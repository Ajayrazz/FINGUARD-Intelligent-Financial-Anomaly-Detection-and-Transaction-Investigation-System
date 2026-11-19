"""RQ4 evaluation of SHAP and LIME on a registered model and a dataset (no labels are used).

Reports: SHAP additivity and determinism; LIME stability across seeds (top-k overlap); SHAP-vs-LIME agreement; and a
deletion test (removing a row's most-attributed features should lower the score more than removing random ones).
"""

import itertools
import json
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.datasets.models import Dataset
from apps.detection.services import build_frame
from apps.model_registry.models import ModelVersion
from ml_engine import explain as mx
from ml_engine import inference
from ml_engine.features import paysim as fp


class Command(BaseCommand):
    help = "Evaluate explanation stability and fidelity (RQ4) for a model version on a dataset."

    def add_arguments(self, parser):
        parser.add_argument("--model", required=True, help="registered model name, e.g. xgb_paysim_core")
        parser.add_argument("--dataset", type=int, required=True)
        parser.add_argument("--top", type=int, default=100, help="highest-scoring rows to explain with SHAP")
        parser.add_argument("--random", type=int, default=100, help="random rows to explain with SHAP")
        parser.add_argument("--lime-rows", type=int, default=30)
        parser.add_argument("--lime-seeds", type=int, default=5)
        parser.add_argument("--out", default="")

    def handle(self, *args, **o):
        version = (
            ModelVersion.objects.filter(model__name=o["model"]).select_related("model").order_by("-trained_at").first()
        )
        ds = Dataset.objects.filter(pk=o["dataset"]).first()
        if version is None or ds is None:
            raise CommandError("unknown model or dataset")
        algorithm = version.model.algorithm
        if algorithm not in mx.SHAP_ALGORITHMS:
            raise CommandError(
                f"{algorithm} is explained with LIME only; this command evaluates SHAP and LIME together"
            )
        model = inference.load_artifact(version.artifact_path, version.artifact_sha256, settings.ML_ARTIFACTS_DIR)
        names = version.feature_schema["features"]
        X = fp.build_features(build_frame(ds))[names].to_numpy()
        score = lambda A: inference.score_matrix(model, algorithm, np.asarray(A))  # noqa: E731
        scores = score(X)
        rng = np.random.default_rng(0)
        top_idx = np.argsort(-scores)[: o["top"]]
        rest = np.setdiff1d(np.arange(len(X)), top_idx)
        rnd_idx = rng.choice(rest, size=min(o["random"], len(rest)), replace=False)
        rows_idx = np.concatenate([top_idx, rnd_idx])
        baseline = np.median(X[rng.choice(len(X), size=min(5000, len(X)), replace=False)], axis=0)
        report: dict = {"model": o["model"], "algorithm": algorithm, "dataset": ds.name, "rows_in_dataset": len(X), "rows_explained": len(rows_idx),
                        "features": names, "score_range_of_explained_rows": [float(scores[rows_idx].min()), float(scores[rows_idx].max())]}  # fmt: skip

        vals, base, space = mx.shap_attribution(model, algorithm, X[rows_idx])
        vals2, _, _ = mx.shap_attribution(model, algorithm, X[rows_idx])
        recon = base + vals.sum(axis=1)
        out_sc = scores[rows_idx]
        recon_prob = 1 / (1 + np.exp(-recon)) if space == "log-odds" else recon
        report["shap"] = {
            "space": space,
            "deterministic": bool(np.array_equal(vals, vals2)),
            "max_additivity_error_in_score": float(np.max(np.abs(recon_prob - out_sc))),
        }

        k_list = [k for k in (1, 2, 3, 5) if k < len(names)]
        fid = {}
        for k in k_list:
            top_drop, rand_drop = mx.deletion_drop(score, X[rows_idx], vals, baseline, k, np.random.default_rng(1))
            fid[f"k={k}"] = {
                "drop_removing_top_k": top_drop,
                "drop_removing_random_k": rand_drop,
                "ratio": top_drop / rand_drop if rand_drop > 1e-12 else None,
            }
        report["shap"]["deletion_test"] = fid

        lime_rows = np.concatenate([top_idx[: o["lime_rows"] // 2], rnd_idx[: o["lime_rows"] - o["lime_rows"] // 2]])
        bg = X[rng.choice(len(X), size=min(500, len(X)), replace=False)]
        j3, j5, agree3, sign = [], [], [], []
        lime_mat = np.zeros((len(lime_rows), len(names)))
        for r, i in enumerate(lime_rows):
            per_seed = [
                mx.lime_attribution(score, bg, X[i], names, seed=s, num_samples=2000, k=len(names))
                for s in range(o["lime_seeds"])
            ]
            for a, b in itertools.combinations(per_seed, 2):
                ta, tb = [f for f, _, _ in a][:3], [f for f, _, _ in b][:3]
                j3.append(mx.topk_jaccard(ta, tb))
                j5.append(mx.topk_jaccard([f for f, _, _ in a][:5], [f for f, _, _ in b][:5]))
                wa, wb = dict((f, w) for f, w, _ in a), dict((f, w) for f, w, _ in b)
                sign.append(
                    np.mean([np.sign(wa[f]) == np.sign(wb[f]) for f in names if wa[f] != 0 and wb[f] != 0] or [1.0])
                )
            first = per_seed[0]
            for f, w, _ in first:
                lime_mat[r, names.index(f)] = w
            shap_top = [n for n, _ in mx.top_features(vals[list(rows_idx).index(i)], names, 3)]
            agree3.append(mx.topk_jaccard(shap_top, [f for f, _, _ in first][:3]))
        report["lime"] = {"rows": len(lime_rows), "seeds": o["lime_seeds"], "top3_overlap_between_seeds": float(np.mean(j3)), "top5_overlap_between_seeds": float(np.mean(j5)),
                          "sign_agreement_between_seeds": float(np.mean(sign)), "top3_overlap_with_shap": float(np.mean(agree3))}  # fmt: skip
        lfid = {}
        for k in k_list:
            t, r_ = mx.deletion_drop(score, X[lime_rows], lime_mat, baseline, k, np.random.default_rng(1))
            sv = vals[[list(rows_idx).index(i) for i in lime_rows]]
            ts, rs = mx.deletion_drop(score, X[lime_rows], sv, baseline, k, np.random.default_rng(1))
            lfid[f"k={k}"] = {"lime_drop_top_k": t, "shap_drop_top_k_same_rows": ts, "random_drop": r_}
        report["lime"]["deletion_test_same_rows"] = lfid
        mean_abs = np.abs(vals).mean(axis=0)
        report["global_top_features_by_mean_abs_shap"] = [
            (names[i], float(mean_abs[i])) for i in np.argsort(-mean_abs)[:5]
        ]
        text = json.dumps(report, indent=2)
        self.stdout.write(text)
        if o["out"]:
            Path(o["out"]).write_text(text)
