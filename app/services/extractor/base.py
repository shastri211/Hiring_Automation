from abc import ABC, abstractmethod

class BaseOCREngine(ABC):
    @abstractmethod
    async def extract_text_from_image(self, file_path: str) -> str:
        pass

class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: str) -> str:
        pass
