# Solna

A full-stack web application built with React, TypeScript, Express.js, and PostgreSQL. The project includes file monitoring capabilities with SFTP integration and is fully containerized using Docker.

## 🚀 Features

- **Frontend**: Modern React application with TypeScript and Vite for fast development
- **Backend**: Express.js API server with TypeScript support
- **Database**: PostgreSQL database for data persistence
- **File Monitoring**: SFTP server with automated file watching and processing
- **Containerization**: Complete Docker Compose setup for easy deployment
- **Hot Reload**: Development environment with hot module replacement

## 📋 Prerequisites

Before running this project, make sure you have the following installed:

- **Node.js** (version 16 or higher)
- **npm** (comes with Node.js)
- **Docker** and **Docker Compose**
- **Git** (for cloning the repository)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd solna
```

### 2. Install Dependencies (Optional - for local development)

If you want to run the project locally without Docker:

```bash
# Install frontend dependencies
cd frontend
npm install

# Install server dependencies
cd ../server
npm install
```

## 🚀 Running the Project

### Using Docker Compose (Recommended)

The easiest way to run the entire application:

```bash
# Start all services
docker-compose up

# Start services in detached mode (background)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Running Locally (Development)

If you prefer to run services individually:

**1. Start the database:**

```bash
docker-compose up db -d
```

**2. Start the backend server:**

```bash
cd server
npm run dev
```

**3. Start the frontend (in a new terminal):**

```bash
cd frontend
npm run dev
```

## 🌐 Accessing the Application

Once the application is running:

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:3000
- **Database**: localhost:5432 (if running locally)

## 📁 Project Structure

```
solna/
├── frontend/                 # React + TypeScript frontend
│   ├── src/                 # Source code
│   ├── public/              # Static assets
│   ├── package.json         # Frontend dependencies
│   └── dockerfile           # Frontend Docker configuration
├── server/                  # Express.js backend
│   ├── src/                 # Server source code
│   ├── scripts/             # Utility scripts
│   ├── package.json         # Server dependencies
│   └── dockerfile           # Server Docker configuration
├── local_data/              # SFTP upload directory
├── docker-compose.yml       # Docker services configuration
└── README.md               # This file
```

## 💻 Usage Examples

### Frontend Development

The frontend is a React application with TypeScript. Key commands:

```bash
cd frontend

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Preview production build
npm run preview
```

### Backend Development

The backend is an Express.js server with TypeScript:

```bash
cd server

# Start development server with hot reload
npm run dev

# Build TypeScript to JavaScript
npm run build

# Start production server
npm start
```

### API Endpoints

The server currently provides:

- `GET /` - Returns "Hello World!" message

## 🐳 Docker Services

The application consists of several Docker services:

- **db**: PostgreSQL database
- **api**: Express.js backend server
- **frontend**: React frontend application
- **sftp**: SFTP server for file uploads
- **watcher**: File monitoring service
