from langchain_community.document_loaders import UnstructuredWordDocumentLoader, DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Import Gemini specific classes
from langchain_cohere import CohereEmbeddings, ChatCohere
from langchain_pinecone import Pinecone as LangchainPinecone
from langchain.chains import RetrievalQA, create_retrieval_chain, create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from pinecone import Pinecone
import os
import logging
import time
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
import nltk
from nltk.corpus import wordnet, stopwords
from nltk.tokenize import word_tokenize
import string
import json

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download NLTK data
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class RAGChatbot:
    """
    A Retrieval-Augmented Generation (RAG) chatbot that uses Gemini models to answer questions
    based on provided documents.

    The chatbot uses:
    - Gemini Pro for question answering
    - Gemini embedding model for document embeddings
    - Pinecone vector database for similarity search

    Args:
        docs_path (str): Path to the directory containing the documents (.docx files)
    
    Environment Variables Required:
        - GEMINI_API_KEY: Google Gemini API key
        - PINECONE_API_KEY: Pinecone API key
        - PINECONE_ENV: Pinecone environment (e.g., "us-east-1")
        - PINECONE_INDEX_NAME: Name of the Pinecone index
        - PINECONE_HOST: Host URL for the Pinecone index
    """

    def __init__(self, docs_path: str):
        # Load and validate environment variables
        self.cohere_api_key = os.getenv("COHERE_API_KEY") # Load Cohere API key
        # Removed gemini_api_key loading
        self.pinecone_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV")
        self.pinecone_index = os.getenv("PINECONE_INDEX_NAME")
        self.pinecone_host = os.getenv("PINECONE_HOST")
        
        # Validate required environment variables
        required_vars = {
            "COHERE_API_KEY": self.cohere_api_key, # Check for Cohere API key
            "PINECONE_API_KEY": self.pinecone_key,
            "PINECONE_ENV": self.pinecone_env,
            "PINECONE_INDEX_NAME": self.pinecone_index,
            "PINECONE_HOST": self.pinecone_host
        }
        
        missing_vars = [k for k, v in required_vars.items() if not v]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        self.docs_path = Path(docs_path)
        # Initialize Pinecone client
        logger.info("Initializing Pinecone connection...")
        self.pc = Pinecone(
            api_key=self.pinecone_key,
            environment=self.pinecone_env
        )
        
        # Initialize embeddings
        self._setup_embeddings()
        
        # Initialize document processing components
        self._setup_document_processing_components()
        
        # Initialize vector store
        self._setup_vector_store()
        
        # Initialize QA chain
        self._setup_qa_chains()

        self.texts = [] # To store processed texts (still needed for add_document logic)

    def _setup_embeddings(self):
        """Initialize embedding model."""
        start_time = time.time()
        try:
            self.embeddings = CohereEmbeddings(
                model="embed-multilingual-v3.0", # User specified embedding model
                cohere_api_key=self.cohere_api_key
            )
            logger.info("Initialized Cohere embeddings")
        except Exception as e:
            logger.error(f"Error setting up embeddings: {str(e)}")
            raise

    def _setup_document_processing_components(self):
        """Initialize document processing components."""
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, # Reduced chunk size
            chunk_overlap=100, # Reduced chunk overlap
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        logger.info("Initialized text splitter.")

    def _setup_vector_store(self):
        """Initialize Pinecone vector store."""
        start_time = time.time()
        try:
            # Check if any indexes exist
            indexes = self.pc.list_indexes()
            if not indexes.names():
                logger.error("No Pinecone indexes found. Please create one in the Pinecone Console.")
                raise ValueError("No Pinecone indexes available")

            # Check if our index exists
            if self.pinecone_index not in indexes.names():
                logger.info(f"Index '{self.pinecone_index}' does not exist. Creating it...")
                # Dimension should match the embedding model's output dimension.
                # Cohere's embed-multilingual-v3.0 has a dimension of 1024.
                self.pc.create_index(
                    name=self.pinecone_index,
                    dimension=1024,  # Update dimension for Cohere embeddings
                    metric="cosine",
                )
                logger.info(f"Index '{self.pinecone_index}' created successfully.")

            # Get the Pinecone index
            index = self.pc.Index(self.pinecone_index)
            logger.info(f"Using existing Pinecone index: {self.pinecone_index}")
            
            # Initialize vector store
            self.vectorstore = LangchainPinecone.from_existing_index(
                index_name=self.pinecone_index,
                embedding=self.embeddings,
                text_key="text"            )
            logger.info("Vector store initialized")
        except Exception as e:
            logger.error(f"Error setting up vector store: {str(e)}")
            raise

    def _setup_qa_chains(self):
        """Initialize QA chain with Cohere LLM and history-aware retriever."""
        start_time = time.time()
        try:
            # Initialize Cohere LLM
            self.cohere_llm = ChatCohere(
                model="command-r-plus",
                cohere_api_key=self.cohere_api_key
            )
            
            # Configure retriever with search parameters
            self.retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 10}
            )

            # Contextualize question prompt
            contextualize_q_system_prompt = """Given the following conversation and a follow-up question,
            rephrase the follow-up question to be a standalone question.
            If the follow-up question is already a standalone question, return it as is.
            Do NOT answer the question, just rephrase it if necessary."""
            contextualize_q_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", contextualize_q_system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )
            self.history_aware_retriever = create_history_aware_retriever(
                self.cohere_llm, self.retriever, contextualize_q_prompt
            )

            # Answer question prompt
            qa_system_prompt = """You are a knowledgeable Unani medicine assistant based on the classical text "Firdous ul Hikmat." Your role is to help users understand traditional herbal medicine and natural healing practices.

            ## Your Capabilities:
            - Provide information about medicinal herbs and their therapeutic properties
            - Explain disease-herb relationships from Unani medicine perspective
            - Share traditional remedies and preparation methods
            - Discuss Unani medical principles and concepts
            - Offer historical context about classical Islamic medicine

            ## Guidelines:
            1. **Accuracy First**: Only provide information that can be found in or directly relates to Firdous ul Hikmat
            2. **Cultural Sensitivity**: Respect the traditional Islamic medicine context and terminology
            3. **Safety Disclaimer**: Always remind users to consult healthcare professionals before using any herbal remedies
            4. **Language Support**: Be prepared to discuss Urdu/Arabic herb names alongside their common names
            5. **Educational Focus**: Emphasize learning and understanding rather than prescribing treatments

            ## Response Style:
            - Be informative yet accessible
            - Use clear explanations for complex medical concepts
            - Provide context about Unani medicine traditions when relevant
            - Include both traditional and modern perspectives where appropriate
            - Maintain a respectful, scholarly tone

            ## Important Disclaimers:
            - This information is for educational purposes only
            - Always consult qualified healthcare providers for medical advice
            - Traditional remedies should complement, not replace, modern medical care
            - Individual responses to herbs may vary

            Remember: You are a bridge between classical wisdom and modern understanding, helping preserve and share traditional knowledge responsibly.

            **Context:**
            {context}"""
            qa_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", qa_system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )

            # Create a prompt for formatting each retrieved document to include metadata
            document_prompt = PromptTemplate.from_template(
                "Source: {source}, Page: {page}\n\n{page_content}"
            )
            
            # Build the document chain with the document_prompt
            question_answer_chain = create_stuff_documents_chain(
                self.cohere_llm, qa_prompt, document_prompt=document_prompt
            )
            
            self.qa_chain = create_retrieval_chain(self.history_aware_retriever, question_answer_chain)
            logger.info("QA chain initialized with history-aware retriever and detailed formatting.")
            
        except Exception as e:
            logger.error(f"Error setting up QA chain: {str(e)}")
            raise

    def ask(self, question: str, chat_history: Optional[List[dict]] = None) -> str:
        """
        Ask a question, get a JSON response from the model, and format it.
        """
        start_time = time.time()
        try:
            logger.info(f"Asking question: {question}")

            # Convert chat_history from list of dicts to Langchain message objects
            lc_chat_history = []
            if chat_history:
                for msg in chat_history:
                    if msg['role'] == 'user':
                        lc_chat_history.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'bot':
                        lc_chat_history.append(AIMessage(content=msg['content']))

            # Get the raw JSON response from the model
            response = self.qa_chain.invoke({"input": question, "chat_history": lc_chat_history})
            raw_answer = response['answer']
            logger.info(f"Raw model response: {raw_answer}")

            # Remove asterisks from the response
            cleaned_answer = raw_answer.replace('*', '')
            
            return cleaned_answer.replace('\n', '<br>')

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    def ask_stream(self, question: str, chat_history: Optional[List[dict]] = None):
        """
        Ask a question and stream the response.
        """
        logger.info(f"Streaming question: {question}")
        lc_chat_history = []
        if chat_history:
            for msg in chat_history:
                if msg['role'] == 'user':
                    lc_chat_history.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'bot':
                    lc_chat_history.append(AIMessage(content=msg['content']))
        
        # Use the stream method to get a generator
        for chunk in self.qa_chain.stream({"input": question, "chat_history": lc_chat_history}):
            if 'answer' in chunk:
                yield chunk['answer'].replace('*', '')

    def get_synonyms(self, word):
        """
        Get synonyms for a word using WordNet.
        """
        synonyms = set()
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                synonyms.add(lemma.name())
        return synonyms

    def add_document(self, filepath: str):
        """
        Loads a document from the given filepath, splits it into chunks,
        generates embeddings, and adds it to the Pinecone vector store.
        Initializes components if they haven't been already.
        """
        logger.info(f"Adding document: {filepath}")
        try:
            # Components are now initialized in __init__

            # Load the document
            loader = PyPDFLoader(filepath)
            documents = loader.load()
            logger.info(f"Loaded document: {len(documents)} pages/chunks from {filepath}")
            
            # --- DEBUGGING: Print content of first few documents ---
            for i, doc in enumerate(documents[:3]): # Print first 3 documents
                logger.info(f"Content of document {i+1} (first 500 chars):\n{doc.page_content[:500]}")
                if not doc.page_content.strip():
                    logger.warning(f"Document {i+1} has empty or whitespace-only content.")
            # --- END DEBUGGING ---

            # Split the document into chunks
            texts = self.splitter.split_documents(documents)
            logger.info(f"Split document into {len(texts)} text chunks.")
            
            # Add texts to the vector store
            # The add_texts method expects a list of texts and optionally metadata.
            # We are passing the Document objects directly, which Langchain handles.
            if texts:
                logger.info(f"Attempting to add {len(texts)} chunks to Pinecone...")
                self.vectorstore.add_texts([doc.page_content for doc in texts], metadatas=[doc.metadata for doc in texts])
                logger.info(f"Successfully added {len(texts)} chunks to Pinecone.")
            else:
                logger.warning("No text chunks generated from the document. Nothing to add to Pinecone.")
            
            # Update the internal list of texts
            self.texts.extend(texts)
            
        except Exception as e:
            logger.error(f"Error adding document {filepath}: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        # Initialize the chatbot with the docs path
        print("Initializing chatbot... This may take a moment.")
        chatbot = RAGChatbot("docs/")
        print("\nChatbot ready! You can now upload PDFs and ask questions.")
        print("Type 'quit' or 'exit' to end the conversation.\n")
        
        while True:
            # Get user input
            question = input("\nYour question: ").strip()
            
            # Check if user wants to quit
            if question.lower() in ['quit', 'exit']:
                print("\nThank you for using the chatbot. Goodbye!")
                break
            
            # Skip empty questions
            if not question:
                print("Please ask a question.")
                continue
            
            try:
                # Get and print the response
                response = chatbot.ask(question)
                print(f"\nAnswer: {response}")
            except Exception as e:
                print(f"\nError: Unable to get response - {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise
