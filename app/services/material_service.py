import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Material
from app.repositories.material_repository import MaterialRepository
from app.schemas.material import MaterialCreate, MaterialUpdate

logger = logging.getLogger(__name__)


class MaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MaterialRepository(db)

    def get(self, material_id: int) -> Material:
        material = self.repo.get(material_id)
        if material is None:
            raise NotFoundError("Material", material_id)
        return material

    def search(self, **filters) -> tuple[list[Material], int]:
        return self.repo.search(**filters)

    def create(self, data: MaterialCreate) -> Material:
        if self.repo.get_by_sku(data.sku):
            raise ConflictError(f"A material with SKU '{data.sku}' already exists")
        material = self.repo.add(Material(**data.model_dump()))
        self.db.commit()
        self.db.refresh(material)
        logger.info("material created id=%s", material.id)
        return material

    def patch(self, material_id: int, data: MaterialUpdate) -> Material:
        material = self.get(material_id)
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(material, field, value)
        self.db.commit()
        self.db.refresh(material)
        return material
