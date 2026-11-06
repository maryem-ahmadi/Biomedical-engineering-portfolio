# Sahet Sghiri - Child Health Monitoring Platform

**A digital platform for pediatric health monitoring and support.**

## Project Overview

Sahet Sghiri is a web application designed to support child health monitoring by connecting parents and healthcare professionals through a centralized platform.

The project combines web development, medical information management, and an AI-powered conversational assistant based on Retrieval-Augmented Generation (RAG).

## Key Features

### Parent Space
- Child profile management.
- Growth and health monitoring.
- Vaccination schedule tracking.
- Appointment requests.
- Access to prescriptions and follow-up information.

### Healthcare Professional Space
- Patient record consultation.
- Medical consultation management.
- Prescription creation.
- Appointment and availability management.

### Administrator Space
- User and platform management.
- Administrative dashboard.

### AI-Powered Medical Chatbot
- Retrieval-Augmented Generation (RAG).
- FAISS vector search.
- Mistral-7B-Instruct-v0.3 language model.
- Multilingual embeddings using Sentence Transformers.
- Pediatric medical knowledge base.

## Technologies Used

| Category | Technologies |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, Bootstrap 5, Jinja2 |
| Database | SQLite, SQLAlchemy |
| AI / NLP | Mistral-7B, Transformers |
| RAG | FAISS, LangChain |
| Embeddings | Sentence Transformers |

## Project Structure

Sahet-Sghiri/
â”œâ”€â”€ app.py
â”œâ”€â”€ run_now.py
â”œâ”€â”€ find_auto.py
â”œâ”€â”€ ia/
â”‚   â””â”€â”€ chatbot.py
â”œâ”€â”€ templates/
â”œâ”€â”€ static/
â”‚   â””â”€â”€ style.css
â”œâ”€â”€ interface/
â””â”€â”€ mes_documents_word/
