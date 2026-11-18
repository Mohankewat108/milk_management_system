from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateFileSystemStorage(FileSystemStorage):
    """Store uploads outside MEDIA_ROOT and never expose a public URL."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", settings.BASE_DIR / "private_uploads")
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError("Private files must be served through an authorised view.")


private_storage = PrivateFileSystemStorage()
