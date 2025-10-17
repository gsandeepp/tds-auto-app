# Auto Deployment Agent

**Version:** 0.1.0  
**Author:** [G Sandeepp](https://github.com/gsandeepp)  
**License:** MIT  

---

## Summary

The **Auto Deployment Agent** is a FastAPI-based service that receives task requests, generates minimal web applications using an LLM, and deploys them to GitHub Pages. It supports multiple rounds of updates, automatically pushes changes to GitHub repositories, and optionally notifies an evaluation endpoint with repo and deployment metadata.

This tool is intended for educational purposes in LLM-assisted code generation and automated deployment workflows.

---

## Features

- Accepts JSON POST requests containing task brief, secret, and optional attachments.
- Verifies the student-provided secret for security.
- Generates app files using OpenAI GPT-4o-mini, with a fallback generator.
- Creates or updates GitHub repositories using a personal access token.
- Automatically adds a `README.md` and MIT `LICENSE`.
- Deploys applications via GitHub Pages.
- Supports multi-round updates (`round 1`, `round 2`, etc.).
- Sends deployment metadata to an evaluation endpoint.

---

## Setup

### Prerequisites

- Python 3.10+
- GitHub personal access token with `repo` and `workflow` permissions.
- OpenAI API key.
- (Optional) Evaluation server URL.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gsandeepp/auto-deployment-agent.git
   cd auto-deployment-agent
