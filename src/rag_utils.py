import os
from typing import List, Dict
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Pinecone
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from pinecone import Pinecone as PineconeClient, ServerlessSpec
from dotenv import load_dotenv
import logging
import uuid
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT")

# Initialize Pinecone
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is not set")

pc = PineconeClient(api_key=PINECONE_API_KEY)

# Initialize OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Constants
INDEX_NAME = os.getenv("PINECONE_INDEX")
NAMESPACE = "default"

class RAGManager:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=OPENAI_API_KEY,
            model="text-embedding-3-large"  # This model produces 3072-dimensional embeddings
        )
        self.llm = ChatOpenAI(
            temperature=0.7,
            model_name="gpt-4o-mini",
            openai_api_key=OPENAI_API_KEY,
            tags=["teamflow", "chat", "slacker"]  # Add tags for LangSmith
        )
        
        # Initialize Pinecone vector store
        try:
            # Get list of existing indexes
            existing_indexes = [index_info['name'] for index_info in pc.list_indexes()]
            logger.info(f"Existing Pinecone indexes: {existing_indexes}")

            # Create index if it doesn't exist
            if INDEX_NAME not in existing_indexes:
                logger.info(f"Creating new Pinecone index: {INDEX_NAME}")
                pc.create_index(
                    name=INDEX_NAME,
                    dimension=1536,  # OpenAI embedding dimension
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-west-2'
                    )
                )
                # Wait for index to be ready
                while not pc.describe_index(INDEX_NAME).status['ready']:
                    time.sleep(1)

            self.index = pc.Index(INDEX_NAME)
            logger.info(f"Successfully connected to Pinecone index: {INDEX_NAME}")
            
            self.vectorstore = Pinecone.from_existing_index(
                index_name=INDEX_NAME,
                embedding=self.embeddings,
                namespace=NAMESPACE
            )
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}", exc_info=True)
            raise
        
        # Set up memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"  # Explicitly tell memory to store the 'answer' output
        )
        
        # Initialize the RAG chain
        self.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vectorstore.as_retriever(
                search_kwargs={"k": 3}
            ),
            memory=self.memory,
            return_source_documents=True,
            verbose=True  # Add verbosity for better LangSmith tracing
        )
    
    def query(self, question: str, chat_history: List = None) -> Dict:
        """
        Process a question using the RAG system
        """
        if chat_history is None:
            chat_history = []
            
        try:
            # Get response from the chain
            response = self.qa_chain(
                {"question": question, "chat_history": chat_history},
                run_name=f"TeamFlow RAG Query - {question[:50]}..."  # Add run name for LangSmith
            )
            
            # Extract source documents
            sources = []
            for doc in response.get("source_documents", []):
                if hasattr(doc, "metadata"):
                    sources.append({
                        "file": doc.metadata.get("source", "Unknown"),
                        "content": doc.page_content
                    })
            
            return {
                "answer": response["answer"],
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error in query: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "answer": "Sorry, I encountered an error while processing your question."
            }
    
    def add_documents(self, texts: List[str], metadatas: List[Dict] = None):
        """
        Add new documents to the vector store by upserting them to the Pinecone index
        
        Args:
            texts: List of text content to be embedded and stored
            metadatas: Optional list of metadata dictionaries for each text
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Starting document ingestion for {len(texts)} texts")
            
            # Generate embeddings for the texts
            embeddings = self.embeddings.embed_documents(texts)
            logger.info(f"Generated embeddings of dimension {len(embeddings[0])}")
            
            # Prepare vectors for upsertion
            vectors = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                # Generate a unique ID for each vector
                vector_id = str(uuid.uuid4())
                
                # Prepare metadata
                metadata = metadatas[i] if metadatas else {}
                # Truncate text if it's too long (Pinecone has metadata size limits)
                truncated_text = text[:3500] if len(text) > 3500 else text
                metadata["text"] = truncated_text
                
                vector = {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata
                }
                vectors.append(vector)
            
            logger.info(f"Prepared {len(vectors)} vectors for upsertion")
            
            # Upsert vectors in batches of 100
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                logger.info(f"Upserting batch {i//batch_size + 1} of {(len(vectors)-1)//batch_size + 1}")
                try:
                    response = self.index.upsert(
                        vectors=batch,
                        namespace=NAMESPACE
                    )
                    logger.info(f"Upsert response: {response}")
                except Exception as batch_error:
                    logger.error(f"Error upserting batch: {str(batch_error)}", exc_info=True)
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error upserting documents: {str(e)}", exc_info=True)
            return False

# Create a singleton instance
rag_manager = RAGManager()