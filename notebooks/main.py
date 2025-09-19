import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Fix for OpenMP error on macOS

import streamlit as st
import time
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredURLLoader
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: check if API key was loaded
if not os.getenv("OPENAI_API_KEY"):
    st.error("⚠️ Kein OPENAI_API_KEY gefunden! Bitte prüfe deine .env Datei.")
else:
    print("API Key geladen.")

# Sprache auswählen
language = st.sidebar.radio("Language / Sprache", ["Deutsch", "English"])

# Texte dynamisch abhängig von Sprache
if language == "Deutsch":
    title = "MedAI Literatur Explorer"
    source_label = "Quelle auswählen:"
    url_label = "URL"
    pdf_label = "Lade eine oder mehrere PDFs hoch"
    process_button = "Daten verarbeiten"
    query_label = "❓ Frage eingeben:"
    summarize_button = "🔍 Zusammenfassung aller Quellen erstellen"
    answer_label = "Antwort"
    sources_label = "Quellen:"
    summary_label = "Zusammenfassung"
    fallback_message = "In den geladenen Quellen konnte ich keine relevanten Informationen finden. Bitte probieren Sie eine andere Frage oder andere Quelle."
else:
    title = "MedAI Literature Explorer"
    source_label = "Select source:"
    url_label = "URL"
    pdf_label = "Upload one or more PDFs"
    process_button = "Process Data"
    query_label = "❓ Ask a question:"
    summarize_button = "🔍 Summarize all sources"
    answer_label = "Answer"
    sources_label = "Sources:"
    summary_label = "Summary"
    fallback_message = "No relevant information found in the loaded sources. Please try a different question or source."

# Titel
st.title(title)
st.sidebar.title("Settings")

# Auswahl: URL oder PDF
source_type = st.sidebar.radio(source_label, ["URL", "PDF"])

urls, uploaded_files = [], []
if source_type == "URL":
    for i in range(3):
        default_url = "https://www.nature.com/articles/s41467-025-59123-4" if i == 0 else ""
        url = st.sidebar.text_input(f"{url_label} {i+1}", value=default_url)
        if url:
            urls.append(url)
elif source_type == "PDF":
    uploaded_files = st.sidebar.file_uploader(
        pdf_label,
        type=["pdf"],
        accept_multiple_files=True
    )

process_data_clicked = st.sidebar.button(process_button)
faiss_path = "faiss_store_openai"

main_placeholder = st.empty()

# LLM Setup
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.6,
    max_tokens=500,
    api_key=os.getenv("OPENAI_API_KEY")
)

if process_data_clicked:
    docs = []

    # Lade URLs
    if urls:
        loader = UnstructuredURLLoader(urls=urls)
        main_placeholder.text("Data Loading (URLs)...")
        docs.extend(loader.load())

    # Lade PDFs
    if uploaded_files:
        for pdf in uploaded_files:
            pdf_path = os.path.join("temp", pdf.name)
            os.makedirs("temp", exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(pdf.read())
            loader = PyPDFLoader(pdf_path)
            main_placeholder.text(f"Loading PDF: {pdf.name}...")
            docs.extend(loader.load())

    # Split Documents
    text_splitter = RecursiveCharacterTextSplitter(
        separators=['\n\n', '\n', '.', ','],
        chunk_size=1000
    )
    main_placeholder.text("Text Splitter...Started...")
    docs = text_splitter.split_documents(docs)

    # Embeddings + FAISS
    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectorstore_openai = FAISS.from_documents(docs, embeddings)
    main_placeholder.text("Embedding Vector Started Building...")
    time.sleep(2)

    vectorstore_openai.save_local(faiss_path)

# Query Input
query = st.text_input(query_label)
summarize_clicked = st.button(summarize_button)

if os.path.exists(faiss_path):
    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectorstore = FAISS.load_local(
        faiss_path,
        embeddings,
        allow_dangerous_deserialization=True
    )

    retriever = vectorstore.as_retriever()
    chain = RetrievalQAWithSourcesChain.from_llm(llm=llm, retriever=retriever)

    # Q&A Modus
    if query:
        result = chain.invoke({"question": query})

        st.header(answer_label)
        answer_text = result["answer"]
        if not answer_text or "weiß es nicht" in answer_text or "don't know" in answer_text.lower():
            st.write(fallback_message)
        else:
            st.write(answer_text)

        sources = result.get("sources", "")
        if sources:
            st.subheader(sources_label)
            for source in sources.split("\n"):
                st.write(source)

    # Summarizer-Modus
    if summarize_clicked:
        summary_prompt = (
            "Fasse die wichtigsten Punkte aus den geladenen Dokumenten zusammen."
            if language == "Deutsch"
            else "Summarize the key points from the loaded documents."
        )

        result = chain.invoke({"question": summary_prompt})

        st.header(summary_label)
        st.write(result["answer"])
