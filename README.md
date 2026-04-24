# Invisio

**Invisio** is a web-based, AI-powered image editing platform designed to make advanced visual editing accessible to everyone.  
It combines **AI automation** with a **human-in-the-loop refinement workflow**, allowing users to generate fast results while still correcting minor inaccuracies when needed.

Unlike traditional editing tools that require technical expertise or fully automated systems that offer little control, Invisio aims to provide a balanced experience focused on **usability, privacy, modularity, and responsible AI-assisted editing**.

---

## Overview

Invisio is built as a modern client-server system for AI-assisted image editing.  
Users can upload an image, choose an editing operation, preview the result, optionally refine AI-generated masks, and download the final output through a simple web interface.

The platform is designed around the following principles:

- **Accessibility for non-technical users**
- **AI-first editing with limited corrective user control**
- **Privacy-by-design and temporary session-based processing**
- **Modular architecture for extensibility**
- **Responsible and safety-aware AI usage**

---

## 📚 Project Documentation

These documents cover the complete development process of **Invisio**.

| Document | Description |
|---|---|
| [Final Report](./docs/OrionAi_YAP496_Final_Report.pdf) | Main and final academic report of the project. |
| [PKE Report](./docs/Invisio_PKE_Raporu_YAP496.pdf) | Constraints, standards compliance, and impact analysis. |
| [Project Proposal](./docs/OrionAI_Project_Proposal.pdf) | Initial project scope and objectives. |
| [Project Specifications Report](./docs/OrionAI_Project_Specifications_Report.pdf) | System description, constraints, and requirements. |
| [Analysis Report](./docs/OrionAI_Analysis_Report.pdf) | Requirement analysis and system modeling. |
| [High-Level Design Report](./docs/OrionAI_High-Level_Design_Report.pdf) | Overall architecture and subsystem design. |
| [Low-Level Design Report](./docs/OrionAI_Low-Level_Design_Report.pdf) | Detailed design of classes, interfaces, and components. |
| [Test Plan Report](./docs/OrionAI_Test_Plan_Report.pdf) | Testing methodology, cases, and evaluation plan. |

---

## ✨ Key Features

### 🪄 AI Object Removal
Intelligent object removal powered by mask-guided inpainting workflows.  
Reconstructs removed regions with visually coherent background completion.

### 🌄 Background Removal & Replacement
Automatic foreground segmentation for clean background isolation.  
Supports both background removal and replacement workflows for flexible scene editing.

### 🎨 Smart Image Enhancement
Enhances image quality through brightness, contrast, color correction, denoising, sharpening, and resolution improvement.  
Designed to improve visual clarity while preserving a fast and responsive web experience.

### 😊 Portrait Enhancement & Beautification
Face-aware enhancement pipeline for clearer and more polished portrait results.  
Supports facial beautification with natural-looking smoothing and localized refinements.

### ⏳ Age Transformation
Applies aging and rejuvenation effects through region-aware facial processing.  
Uses efficient mask-based transformations for realistic texture and tone changes.

### 👁️ Face Feature Editing
Supports localized face editing operations such as eye, nose, and mouth/lip adjustments.  
Built on face-aware landmark analysis for controlled and targeted modifications.

### 🎨 Hair Editing
Includes hair-region segmentation for appearance-oriented edits such as hair color transformation.  
Designed as a lightweight, region-based editing workflow.

### 🖌️ Neural Style Transfer
Applies artistic styles to images while preserving the original content structure.  
Enables creative visual transformations through dedicated style transfer pipelines.

### 🌈 AI Colorization
Automatically colorizes grayscale images using deep learning-based color mapping.  
Produces vivid colorized outputs while preserving the original image composition.

### ✍️ Human-in-the-Loop Refinement
Allows users to correct AI-generated masks with intuitive brush-based refinement tools.  
Improves difficult edge cases without exposing pixel-level professional editing complexity.

### 👀 Preview Before Export
Users can inspect generated results before finalizing the workflow.  
Makes the editing process more controlled, reversible, and user-friendly.

### 📥 Export & Download
Supports final image export and download through a standardized output pipeline.  
Ensures processed results are easy to access and save in a clean workflow.

### 🌐 Community Sharing
Optionally allows users to share selected final outputs in a public community gallery.  
Designed as a consent-based feature separated from the core private editing workflow.

### 🔒 Privacy-First Architecture
All images are processed in temporary session-based workflows instead of being stored permanently by default.  
Built with privacy-by-design principles aligned with GDPR and KVKK-oriented thinking.

### 🛡️ Safety & Input Validation
Includes structured validation for file format, file size, and unsafe content detection before AI processing begins.  
Helps protect system resources and prevents restricted content from entering the editing pipeline.

---

## Problem Statement

Current image editing solutions generally fall into two categories:

- **Professional tools** provide precise control but require expertise, time, and complex workflows.
- **Fully automated AI tools** are fast and easy to use, but users often cannot correct mistakes in generated outputs.

Invisio addresses this gap by introducing a **hybrid AI-assisted workflow** where AI performs the main image transformation and the user can provide limited, intuitive corrections when needed.

---

## System Architecture

Invisio follows a **distributed client-server architecture** with a strong separation between user interaction and AI processing.

### High-Level Layers

- **Presentation Layer**  
  Handles the web interface, image upload, editing options, previews, refinement interaction, and download experience.

- **Control Layer**  
  Coordinates requests, validates inputs, manages sessions, and routes editing operations to the appropriate processing modules.

- **Processing Layer**  
  Executes AI-driven image editing workflows such as segmentation, inpainting, enhancement, colorization, and style transfer.

- **Resource Layer**  
  Manages computational resources such as CPU/GPU-backed inference execution and runtime processing efficiency.

### Architectural Characteristics

- Modular and extensible design
- MVC-inspired separation of concerns
- Session-based temporary data handling
- Asynchronous and non-blocking processing flow
- Privacy-oriented and safety-aware system design

---

## Core Workflow

The typical user flow in Invisio is:

1. Upload an image
2. Select one or more AI-based editing operations
3. Let the system process the image
4. Preview the generated output
5. Optionally refine masks if needed
6. Download the final result

This workflow supports both:

- **fully automated editing**
- **hybrid refinement-based editing**

---

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- React Router
- Axios
- Zustand
- Framer Motion
- Lucide React

### Backend
- Python
- FastAPI
- Uvicorn
- Pydantic
- python-multipart

### AI / Image Processing
- PyTorch
- OpenCV
- NumPy
- Pillow
- MediaPipe

### Models / Processing Pipelines
- U2-Net
- MobileSAM
- LaMa
- AdaIN
- ECCV16 Colorization
- EDSR-based enhancement utilities
- NSFW detection pipeline

### Infrastructure / Persistence
- PostgreSQL
- SQLAlchemy
- asyncpg
- Docker
- Docker Compose

### Testing / Development
- pytest
- httpx
- Playwright
- ESLint
- Git / GitHub

---

## Design Patterns

The project applies multiple software engineering principles and design patterns to keep the architecture maintainable and extensible.

### Strategy Pattern
AI editing capabilities are represented through a shared abstraction layer, allowing different processing behaviors to be selected and used interchangeably.

### Facade Pattern
The editing workflow is coordinated through a simplified controller interface that hides the complexity of validation, model selection, session handling, and output generation.

### Factory Pattern
AI model selection and instantiation are centralized through a factory mechanism to improve modularity and support future extensions.

### MVC Architecture
Frontend views, backend controllers, and processing/data models are separated to improve clarity, testability, and maintainability.

---

## Privacy & Security

Invisio is designed with **privacy-by-design** and **security-by-default** principles.

### Privacy
- Images are processed only within temporary sessions
- No persistent storage by default for the standard workflow
- No mandatory account creation for core usage
- Data minimization is prioritized throughout the architecture
- Optional persistence is limited to explicitly user-authorized scenarios such as community sharing

### Security
- HTTPS-based secure communication
- File format and size validation
- Input integrity checks
- Request-level protection
- Rate-limiting compatible architecture
- NSFW content detection before main processing
- Structured error handling with limited internal exposure

---

## Functional Scope

The system supports core editing workflows such as:

- image upload
- object removal
- background removal
- background replacement
- image enhancement
- beautification
- face-aware editing
- hair editing
- age transformation
- colorization
- neural style transfer
- refinement-based correction
- preview generation
- export and download
- optional community sharing

---

## Project Goals

The main goals of the project are:

- To make advanced image editing accessible to non-expert users
- To combine automation with limited user control
- To build a modular and extensible AI-assisted editing platform
- To preserve privacy through session-based temporary data handling
- To support responsible and safety-aware image processing

---

## Example Project Structure

```bash
client/
  src/
    components/
    views/
    services/
    store/

backend/
  app/
    controllers/
    models/
    services/
    routes/
    security/
    sessions/

models/
checkpoints/
```
## Installation

### 1. Clone the repository

```bash
git clone https://github.com/umurozu/TOBBETU-BIL496-Orion-AI-Project.git
cd TOBBETU-BIL496-Orion-AI-Project
database/
docs/
```
### 2. Setup the Frontend
cd client
npm install
npm run dev

### 3. Setup the Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

### 4. Optional: Run with Docker
docker-compose up --build

## Usage

1. Open the web interface.
2. Upload an image.
3. Select an AI-powered editing operation.
4. Wait for the processing to complete.
5. Preview the generated result.
6. Refine the output if needed.
7. Download the final image.

8. ## Limitations

- Invisio currently supports **image-based processing only**.
- The system does **not support video editing or real-time video workflows**.
- An **active internet connection** is required to use the platform.
- Processing performance depends on available **backend computational resources**, especially GPU availability.
- Some advanced features may remain **experimental or partially integrated** depending on the current implementation state.
- The platform is intentionally designed to avoid professional-grade low-level editing complexity in order to preserve usability.

 ## Future Work

- Strengthening quantitative evaluation and benchmarking of AI results
- Improving production-grade scalability and deployment readiness
- Expanding AI model support for additional editing capabilities
- Enhancing authentication, authorization, and advanced access control mechanisms
- Improving the human-in-the-loop refinement experience
- Extending community and sharing features
- Supporting a broader range of user inputs and editing scenarios
- Exploring cross-platform product evolution
- Investigating privacy-preserving personalization mechanisms

## Team

**Orion-AI**

- Mehmet Umur ÖZÜ
- Emre KARADOĞAN
- Kübra ARSLAN
- Fatih BAYAZIT
