from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# Path to the text knowledge base used for retrieval augmented generation
DOCUMENT_PATH = BASE_DIR / "document_rag.txt"
# llama3.1:8b 
# --- LLM configuration ---
LLM_MODEL_NAME = "gpt-oss:120b-cloud"
EMBEDDING_MODEL_NAME = "mxbai-embed-large"
LLM_TEMPERATURE = 0.7

# --- RAG parameters ---
TEXT_SPLITTER_CHUNK_SIZE = 1000
TEXT_SPLITTER_OVERLAP = 200
RETRIEVER_TOP_K = 5

