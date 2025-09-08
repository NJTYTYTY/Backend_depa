# Backend PWA - Fish Farming Pond Management System

## Overview
Backend PWA is a comprehensive FastAPI-based backend system designed for managing fish farming ponds with real-time sensor monitoring, media asset management, and comprehensive testing capabilities. The system provides a robust API for pond management, sensor data collection, real-time communication, and file handling.

## 🚀 Features

### Core Functionality
- **User Authentication & Authorization**: JWT-based authentication with role-based access control
- **Pond Management**: Complete CRUD operations for fish farming ponds
- **Sensor Data Management**: Real-time sensor data collection and processing
- **Media Asset Management**: File upload, storage, and retrieval system
- **Real-time Communication**: WebSocket-based real-time data synchronization
- **Comprehensive Testing System**: Test data generation and execution utilities

### Security Features
- **JWT Authentication**: Secure token-based authentication
- **Role-Based Access Control**: Admin, Owner, Operator, and Viewer roles
- **Account Limiting**: Maximum 10 user accounts enforced
- **Input Validation**: Comprehensive data validation and sanitization
- **File Security**: Secure file upload and storage with validation

### Performance Features
- **Database Optimization**: Proper indexing and query optimization
- **Pagination**: Efficient data retrieval with pagination support
- **Real-time Updates**: WebSocket-based live data synchronization
- **Bulk Operations**: Support for bulk data uploads and operations
- **Caching Support**: Built-in caching capabilities for performance

## 🏗️ System Architecture

The system is built with a modular, scalable architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend PWA                            │
│                    (React/Next.js)                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ HTTP/HTTPS
                      │ WebSocket
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    FastAPI Backend                             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Auth &    │  │   Pond      │  │   Sensor    │            │
│  │   User      │  │ Management  │  │   Data      │            │
│  │ Management  │  │             │  │ Management  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Media     │  │   Testing   │  │ WebSocket   │            │
│  │   Asset     │  │   System    │  │   Manager   │            │
│  │ Management  │  │             │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ SQLAlchemy ORM
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    Database Layer                               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   SQLite    │  │ PostgreSQL  │  │   Redis     │            │
│  │ (Dev/Test)  │  │(Production) │  │ (Cache)     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 📚 Documentation

### Core Documentation
- **[API Specification](API_SPECIFICATION.md)** - Complete API endpoint documentation
- **[System Architecture](SYSTEM_ARCHITECTURE.md)** - Detailed system design and architecture
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Development setup and guidelines

### System-Specific Documentation
- **[Authentication System](AUTH_SYSTEM_README.md)** - User management and authentication
- **[Pond Management](POND_MANAGEMENT_README.md)** - Pond operations and management
- **[Sensor Management](SENSOR_MANAGEMENT_README.md)** - Sensor data collection and processing
- **[WebSocket System](WEBSOCKET_SYSTEM_README.md)** - Real-time communication
- **[Media Asset Management](MEDIA_ASSET_MANAGEMENT_README.md)** - File handling system
- **[Test Request System](TEST_REQUEST_SYSTEM_README.md)** - Testing and validation utilities

## 🛠️ Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git

### Local Development Setup
```bash
# Clone the repository
git clone <repository-url>
cd backend-pwa

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment configuration
cp config.env.example config.env

# Edit configuration file
# Set your database URL, secret keys, etc.

# Create admin user
python create_admin.py

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify Installation
- Open browser and navigate to `http://localhost:8000`
- Check API documentation at `http://localhost:8000/docs`
- Test health endpoint at `http://localhost:8000/health`

## 🔧 Configuration

### Environment Variables
```bash
# Database Configuration
DATABASE_URL=sqlite:///./backend_pwa.db  # Development
# DATABASE_URL=postgresql://user:password@localhost/backend_pwa  # Production

# Security Configuration
SECRET_KEY=your-secure-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Application Configuration
ENVIRONMENT=development  # development/production
DEBUG=true  # true/false
LOG_LEVEL=INFO  # DEBUG/INFO/WARNING/ERROR

# File Storage Configuration
FILE_STORAGE_PATH=./uploads
MAX_FILE_SIZE=104857600  # 100MB in bytes
```

### Database Setup
The system automatically creates all required tables on first run. For production, consider using PostgreSQL:

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE USER backend_user WITH PASSWORD 'secure_password';
CREATE DATABASE backend_pwa OWNER backend_user;
GRANT ALL PRIVILEGES ON DATABASE backend_pwa TO backend_user;
\q
```

## 🚀 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Token refresh
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/me` - Get current user

### Pond Management
- `POST /api/v1/ponds/` - Create pond
- `GET /api/v1/ponds/` - List ponds
- `GET /api/v1/ponds/{pond_id}` - Get pond by ID
- `PUT /api/v1/ponds/{pond_id}` - Update pond
- `DELETE /api/v1/ponds/{pond_id}` - Delete pond
- `GET /api/v1/ponds/statistics` - Pond statistics

### Sensor Data Management
- `POST /api/v1/sensors/` - Create sensor data
- `GET /api/v1/sensors/` - List sensor data
- `GET /api/v1/sensors/{sensor_id}` - Get sensor data by ID
- `PUT /api/v1/sensors/{sensor_id}` - Update sensor data
- `DELETE /api/v1/sensors/{sensor_id}` - Delete sensor data
- `POST /api/v1/sensors/bulk` - Bulk sensor data upload
- `GET /api/v1/sensors/statistics` - Sensor data statistics

### Media Asset Management
- `POST /api/v1/media/upload` - Upload media asset
- `GET /api/v1/media/` - List media assets
- `GET /api/v1/media/{asset_id}` - Get media asset by ID
- `GET /api/v1/media/{asset_id}/download` - Download media asset
- `PUT /api/v1/media/{asset_id}` - Update media asset
- `DELETE /api/v1/media/{asset_id}` - Delete media asset
- `GET /api/v1/media/search` - Search media assets
- `GET /api/v1/media/statistics` - Media asset statistics

### Testing System
- `POST /api/v1/testing/generate` - Generate test data
- `POST /api/v1/testing/execute` - Execute test requests
- `POST /api/v1/testing/execute-comprehensive` - Execute comprehensive test suite
- `POST /api/v1/testing/execute-stress` - Execute stress test
- `GET /api/v1/testing/files` - List test files
- `GET /api/v1/testing/results` - List test results
- `GET /api/v1/testing/health` - Testing system health

### WebSocket Endpoints
- `ws://localhost:8000/ws/{pond_id}` - Real-time communication for specific pond

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_auth.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run tests in parallel
pytest -n auto
```

### Test Data Generation
The system includes comprehensive testing utilities:

```bash
# Generate test data
python -c "
from tests.utils.request_generator import generate_sensor_data
data = generate_sensor_data(pond_id=1, count=100)
print(f'Generated {len(data)} sensor data records')
"

# Execute test requests
python -c "
from tests.utils.request_executor import execute_test_requests
results = execute_test_requests('test_data.json', 'sensor')
print(f'Test execution completed: {len(results)} requests')
"
```

## 🔒 Security Features

### Authentication & Authorization
- **JWT Tokens**: Secure access and refresh token system
- **Role-Based Access Control**: Four user roles with different permissions
- **Password Security**: Bcrypt hashing with salt
- **Token Expiration**: Configurable token lifetimes
- **Account Limiting**: Maximum 10 user accounts

### Data Protection
- **Input Validation**: Comprehensive Pydantic schema validation
- **SQL Injection Prevention**: Parameterized queries with SQLAlchemy
- **XSS Protection**: Input sanitization and output encoding
- **CSRF Protection**: Built-in FastAPI security features

### File Security
- **File Type Validation**: MIME type and extension checking
- **File Size Limits**: Configurable maximum file sizes
- **Secure Storage**: Organized file storage with access control
- **Path Traversal Prevention**: Secure filename generation

## 📊 Performance Features

### Database Optimization
- **Proper Indexing**: Strategic database indexes for common queries
- **Query Optimization**: Efficient SQLAlchemy query patterns
- **Connection Pooling**: Database connection management
- **Batch Operations**: Support for bulk data operations

### API Performance
- **Pagination**: Efficient data retrieval with pagination
- **Response Compression**: Built-in FastAPI compression
- **Caching Support**: Response caching capabilities
- **Background Tasks**: Asynchronous processing for heavy operations

### Real-time Performance
- **WebSocket Management**: Efficient connection handling
- **Message Broadcasting**: Optimized real-time data distribution
- **Connection Cleanup**: Automatic cleanup of inactive connections
- **Heartbeat Monitoring**: Connection health monitoring

## 🚀 Deployment

### Production Deployment
For production deployment, refer to the [Deployment Guide](DEPLOYMENT_GUIDE.md) for detailed instructions including:

- Server preparation and configuration
- Nginx reverse proxy setup
- SSL certificate configuration
- Systemd service configuration
- Monitoring and logging setup
- Backup and maintenance procedures

### Docker Support (Planned)
```dockerfile
# Future Docker support
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Commit your changes: `git commit -m 'feat: add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Coding Standards
- Follow PEP 8 Python style guide
- Use Black formatter for code formatting
- Use isort for import sorting
- Write comprehensive tests
- Document all public APIs
- Follow security best practices

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help
- **Documentation**: Start with the [API Specification](API_SPECIFICATION.md)
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Wiki**: Check the project wiki for additional resources

### Common Issues
- **Database Connection**: Check database URL and credentials
- **Authentication**: Verify JWT token configuration
- **File Uploads**: Check file size limits and storage permissions
- **Performance**: Review database indexes and query optimization

## 🔮 Roadmap

### Planned Features
- **GraphQL Support**: Alternative to REST API
- **Microservices Architecture**: Service decomposition
- **Advanced Caching**: Redis integration for performance
- **Mobile App Support**: Native mobile applications
- **Third-party Integrations**: External service integrations
- **Advanced Analytics**: Data analysis and reporting
- **Machine Learning**: Predictive analytics for pond management

### Technical Improvements
- **Event-Driven Architecture**: Asynchronous event processing
- **Advanced Monitoring**: Prometheus and Grafana integration
- **Load Balancing**: Horizontal scaling support
- **Container Orchestration**: Kubernetes deployment support
- **CI/CD Pipeline**: Automated testing and deployment

## 📊 System Status

### Current Version
- **Version**: 1.0.0
- **Status**: Production Ready
- **Last Updated**: January 2024

### System Health
- **API Endpoints**: 25+ endpoints implemented
- **Database Models**: 4 core models with relationships
- **Test Coverage**: 80%+ test coverage
- **Security**: Comprehensive security implementation
- **Documentation**: 100% API and system documentation

---

**Backend PWA** - A robust, scalable, and secure backend system for fish farming pond management with real-time monitoring capabilities.

For more information, visit the [documentation directory](.) or start with the [API Specification](API_SPECIFICATION.md).
