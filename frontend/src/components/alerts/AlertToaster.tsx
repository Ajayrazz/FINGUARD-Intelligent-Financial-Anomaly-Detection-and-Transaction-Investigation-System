import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { useEvents } from "../../hooks/useEvents";
import { useToast } from "../ui/Toast";

/** Mounted once in the layout: pops a toast for new alerts and refreshes the queue. Silent without alerts.read. */
export function AlertToaster() {
  const { can } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  useEvents((e) => {
    if (!can("alerts.read")) return;
    if (e.type === "alert.created") {
      const d = e.data as { severity?: string; reason?: string };
      toast(
        "success",
        `New ${d.severity ?? ""} alert: ${(d.reason ?? "").slice(0, 120)}`,
      );
    }
    if (e.type === "alert.created" || e.type === "alert.updated") {
      void qc.invalidateQueries({ queryKey: ["alerts"] });
      void qc.invalidateQueries({ queryKey: ["alerts-summary"] });
    }
  });
  return null;
}
