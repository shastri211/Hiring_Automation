import os
import aiofiles
import hashlib
from typing import BinaryIO
from fastapi import UploadFile
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.base_dir = settings.STORAGE_LOCAL_DIR
        os.makedirs(self.base_dir, exist_ok=True)
        
    async def save_file(self, file: UploadFile, prefix: str = "") -> str:
        """Saves file to local filesystem and returns the storage key."""
        filename = file.filename or "unknown"
        storage_key = os.path.join(prefix, filename)
        full_path = os.path.join(self.base_dir, storage_key)
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        await file.seek(0)
        async with aiofiles.open(full_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)
                
        return storage_key

    async def compute_hash(self, file: UploadFile) -> str:
        """Computes SHA-256 hash of the file for duplicate detection."""
        await file.seek(0)
        sha256_hash = hashlib.sha256()
        while chunk := await file.read(4096):
            sha256_hash.update(chunk)
        await file.seek(0)
        return sha256_hash.hexdigest()

    def get_secure_path(self, storage_key: str) -> str:
        """Returns an absolute path if it is safely inside base_dir, else None."""
        full_path = os.path.abspath(os.path.join(self.base_dir, storage_key))
        if not full_path.startswith(os.path.abspath(self.base_dir)):
            return None
        return full_path

storage_service = StorageService()
