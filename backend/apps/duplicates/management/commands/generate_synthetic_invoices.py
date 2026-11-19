from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.duplicates import services
from duplicates_lib import synthetic


class Command(BaseCommand):
    help = (
        "Upload the synthetic invoice set (controlled duplicates) and run OCR + matching. Clearly labelled SYNTHETIC."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="email of the user the uploads are attributed to")

    def handle(self, *args, **opts):
        user = User.objects.filter(email=opts["email"]).first()
        if user is None:
            raise CommandError("unknown user")
        docs, expected = synthetic.build_set()
        for d in docs:
            ext = "png" if d["mime"] == "image/png" else "jpg"
            up = SimpleUploadedFile(f"SYNTHETIC-{d['name']}.{ext}", d["bytes"], content_type=d["mime"])
            doc = services.store_invoice_upload(up, user)
            services.Invoice.objects.get_or_create(document=doc)
            services.process_invoice(doc.pk)
        self.stdout.write(f"processed {len(docs)} synthetic invoices; expected pairs: {len(expected)}")
