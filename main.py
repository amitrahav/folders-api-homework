import os
from pprint import pprint
from typing import List, Optional, Any

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.openapi.models import Response
from pydantic import BaseModel, Field
from fastapi_crudrouter import SQLAlchemyCRUDRouter
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session, backref, relation
from starlette import status

app = FastAPI(
    title="FoldersApiHourOne1",
    version="0.0.1",
)

DATABASE = 'mysql://%s:%s@%s/%s?charset=utf8' % (
    os.environ.get("DB_USER", None),
    os.environ.get("DB_PASS", None),
    os.environ.get("DB_HOST", None),
    os.environ.get("DB_NAME", None)
)

engine = create_engine(
    DATABASE,
    echo=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


association_table = Table('association', Base.metadata,
                          Column('sub_id', ForeignKey('folder.id'), primary_key=True),
                          Column('folder_id', ForeignKey('folder.id'), primary_key=True)
                          )


class ProjectModel(Base):
    __tablename__ = 'project'
    id = Column(Integer, primary_key=True, index=True, nullable=False)
    parent_folder_id = Column(Integer, ForeignKey("folder.id"))
    parent_folder = relationship("FolderModel", foreign_keys=parent_folder_id, single_parent=True,
                                 back_populates="projects")
    name = Column(String(16))


class FolderModel(Base):
    __tablename__ = 'folder'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(16), default=None, index=True)
    # sub_folders_id = Column(Integer, ForeignKey("folder.id"))
    parent_folder = Column(Integer, ForeignKey('folder.id'))

    projects = relationship("ProjectModel", back_populates="parent_folder")
    # sub_folders = relationship("FolderModel", foreign_keys="[FolderModel.sub_folders_id]")
    sub_folders = relationship("FolderModel")


Base.metadata.create_all(bind=engine)


class ProjectNoParent(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class SubFolder(BaseModel):
    id: int
    name: str
    projects: Optional[List[ProjectNoParent]] = Field(default=[])
    sub_folders: Optional[List[Any]] = Field(default=[])

    class Config:
        orm_mode = True


class Folder(BaseModel):
    parent_folder: Optional[int] = Field(default=None, alias="parent_folder")
    id: int
    name: str
    projects: Optional[List[ProjectNoParent]] = Field(default=[])
    sub_folders: Optional[List[SubFolder]] = Field(default=[])

    class Config:
        orm_mode = True


class FolderCreate(BaseModel):
    parent_folder: Optional[int] = None
    name: str
    projects: Optional[List[int]] = Field(default=[])
    sub_folders: Optional[List['FolderCreate']] = []


class Project(BaseModel):
    parent_folder: Optional[int] = Field(alias="parent_folder")
    id: int
    name: str

    class Config:
        orm_mode = True


class FolderUpdate(BaseModel):
    parent_folder: Optional[int] = Field(default=None)
    projects: Optional[List[int]] = Field(default=[])
    sub_folders: Optional[List[int]] = Field(default=[])
    name: str


class ProjectCreate(BaseModel):
    name: str

    class Config:
        orm_mode = True



folders_router = SQLAlchemyCRUDRouter(
    schema=Folder,
    update_schema=FolderUpdate,
    create_schema=FolderCreate,
    db_model=FolderModel,
    db=get_db,
    delete_all_route=False,
    prefix="folders",
    paginate=10
)


@folders_router.delete('/{item_id}', responses={status.HTTP_204_NO_CONTENT: {"model": None}})
def delete_folder(item_id: int, db: Session = Depends(get_db)):
    folder_info = db.query(FolderModel).get(item_id)
    if folder_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    db.query(ProjectModel).filter_by(parent_folder_id=item_id).delete(synchronize_session=False)
    db.delete(folder_info)
    db.commit()


@folders_router.post('/{item_id}/projects', response_model=Project)
def add_project_to_folder(
        item_id: int,
        project_request: ProjectCreate,
        db: Session = Depends(get_db)
):
    folder_info = db.query(FolderModel).get(item_id)
    if folder_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    db_project = ProjectModel(name=project_request.name, parent_folder=folder_info)
    db.add(db_project)

    db.commit()
    db.refresh(db_project)

    return db_project


@folders_router.delete('/{item_id}/projects/{project_id}', responses={status.HTTP_204_NO_CONTENT: {"model": None}})
def remove_project_from_folder(
        project_id: int,
        item_id: int,
        db: Session = Depends(get_db)
):
    folder_info = db.query(FolderModel).get(item_id)
    if folder_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    project_info = db.query(ProjectModel).filter_by(parent_folder_id=item_id, id=project_id)
    if project_info.one() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    db.delete(project_info.one())
    db.commit()


@folders_router.get('/{item_id}/projects', response_model=List[Project])
def get_project_from_folder(
        item_id: int,
        db: Session = Depends(get_db)
):
    folder_info = db.query(FolderModel).get(item_id)
    if folder_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    db_project = db.query(ProjectModel).filter_by(parent_folder_id=item_id).all()

    return db_project


@folders_router.put('/{item_id}/projects/{project_id}', response_model=Project)
def update_project_from_folder(
        project_request: ProjectCreate,
        project_id: int,
        item_id: int,
        db: Session = Depends(get_db)
):
    folder_info = db.query(FolderModel).get(item_id)
    if folder_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    project_info = db.query(ProjectModel).filter_by(parent_folder_id=item_id, id=project_id)
    if project_info.one() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project_info.update({"name": project_request.name})
    db.commit()
    db.refresh(project_info.one())

    return project_info.one()


app.include_router(folders_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        reload=True,
        port=80
    )
