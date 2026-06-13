from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
import asyncpg
from database import get_db
from app.services.semantic_index import semantic_indexer
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/orgs/{org_id}/issues", tags=["issues"])

class IssueCreateSchema(BaseModel):
    title: str
    description: str

@router.post("/index")
async def create_and_index_issue(org_id: UUID, issue: IssueCreateSchema, db=Depends(get_db)):
    combined_text = f"{issue.title}\n{issue.description}"
    vector_str = semantic_indexer.encode_text(combined_text)

    async with db.begin():
        issue_id = await db.execute(
            """
            INSERT INTO issues (org_id, title, description)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            str(org_id), issue.title, issue.description
        )
        await db.execute(
            """
            INSERT INTO issue_embeddings (issue_id, chunk_text, embedding, model_version)
            VALUES ($1, $2, $3::vector, 'codebert-base-v1')
            """,
            issue_id, combined_text, vector_str
        )
    
    return {"status": "indexed", "issue_id": issue_id}

@router.post("/search-similar")
async def search_similar_issues(org_id: UUID, payload: IssueCreateSchema, db=Depends(get_db)):
    combined_text = f"{payload.title}\n{payload.description}"
    vector_str = semantic_indexer.encode_text(combined_text)

    query = """
        SELECT
            ie.issue_id,
            ie.chunk_text,
            (ie.embedding <=> $1::vector) AS cosine_distance
        FROM issue_embeddings ie
        INNER JOIN issues i ON ie.issue_id = i.id
        WHERE i.org_id = $2
        ORDER BY embedding <=> $1::vector ASC
        LIMIT 3;
    """

    results = await db.execute(query, vector_str, str(org_id))

    return [
        {
            "issue_id": record["issue_id"],
            "text": record["chunk_text"],
            "score": 1 - record["cosine_distance"]
        }
        for record in results
    ]
