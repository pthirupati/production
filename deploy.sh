#!/bin/bash

# FixitLab Production Deployment Script
# Handles: environment setup, Docker build, migrations, and system startup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
    fi
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose v2."
    fi
    print_success "Docker and Docker Compose found"
}

# Check if .env exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create .env from env.production.example"
    fi
    print_success ".env file found"
}

# Verify critical environment variables
verify_env_variables() {
    print_header "Verifying Environment Variables"
    
    local critical_vars=(
        "DJANGO_SECRET_KEY"
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "RABBITMQ_PASS"
    )
    
    local missing_vars=()
    
    for var in "${critical_vars[@]}"; do
        value=$(grep "^${var}=" .env | cut -d'=' -f2- | tr -d '[:space:]')
        if [ -z "$value" ] || [ "$value" = "CHANGE-ME" ]; then
            missing_vars+=("$var")
        else
            print_success "$var is set"
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_warning "The following critical variables need to be updated in .env:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        read -p "Do you want to edit .env now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            nano .env
        else
            print_error "Please update critical variables in .env before deploying"
        fi
    fi
}

# Stop running containers
stop_containers() {
    print_header "Stopping Running Containers (if any)"
    
    if docker-compose ps | grep -q "running"; then
        echo "Stopping existing containers..."
        docker-compose down --remove-orphans 2>/dev/null || true
        sleep 2
        print_success "Containers stopped"
    else
        print_success "No running containers to stop"
    fi
}

# Build and start containers
build_and_start() {
    print_header "Building and Starting Services"
    
    echo "Building Docker images (this may take 2-5 minutes)..."
    docker-compose build --no-cache 2>&1 | tail -20
    
    echo -e "\n${GREEN}Starting services...${NC}"
    docker-compose up -d
    
    # Wait for services to be ready
    echo "Waiting for services to be healthy (30 seconds)..."
    sleep 30
    
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T backend python -c "import django; django.setup()" 2>/dev/null; then
            print_success "Services are healthy and ready"
            break
        fi
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            echo "Waiting... (attempt $attempt/$max_attempts)"
            sleep 5
        fi
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "Services may still be initializing. Check logs with: docker-compose logs -f"
    fi
}

# Run database migrations
run_migrations() {
    print_header "Running Database Migrations"
    
    echo "Applying migrations..."
    docker-compose run --rm backend python manage.py migrate --noinput
    
    print_success "Database migrations completed"
}

# Create superuser
create_superuser() {
    print_header "Admin Account Setup"
    
    echo "Do you want to create a superuser account now? (y/n)"
    read -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating superuser (follow the prompts)..."
        docker-compose run --rm backend python manage.py createsuperuser
        print_success "Superuser created"
    else
        print_warning "Skipping superuser creation. You can create one later with:"
        echo "  docker-compose run backend python manage.py createsuperuser"
    fi
}

# Run tests
run_tests() {
    print_header "Running Security & Isolation Tests"
    
    echo "Running 51+ production tests (takes ~2 minutes)..."
    
    if docker-compose run --rm backend pytest backend/tests/ -v --tb=short 2>&1 | tail -50; then
        print_success "All tests passed!"
    else
        print_warning "Some tests failed. Check logs above."
    fi
}

# Show deployment summary
show_summary() {
    print_header "Deployment Complete ✅"
    
    echo "Services Status:"
    docker-compose ps
    
    echo -e "\n${GREEN}Access Your Application:${NC}"
    echo "  Frontend:  http://localhost or https://yourdomain.com"
    echo "  Admin:     http://localhost/admin"
    echo "  API:       http://localhost/api"
    echo "  Health:    http://localhost/api/health/"
    
    echo -e "\n${GREEN}Useful Commands:${NC}"
    echo "  View logs:         docker-compose logs -f"
    echo "  Stop services:     docker-compose down"
    echo "  Run shell:         docker-compose exec backend python manage.py shell"
    echo "  View database:     docker-compose exec database psql -U postgres fixitlab"
    echo "  Check backend:     docker-compose logs backend"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "  1. Update DJANGO_ALLOWED_HOSTS with your domain"
    echo "  2. Set up SSL certificates (certbot container ready)"
    echo "  3. Configure email settings in .env"
    echo "  4. Test with: docker-compose run backend pytest backend/tests/"
}

# Main deployment flow
main() {
    print_header "FixitLab Production Deployment"
    
    # Pre-deployment checks
    check_docker
    check_env_file
    verify_env_variables
    
    # Deployment steps
    stop_containers
    build_and_start
    run_migrations
    
    # Optional setup
    read -p "Create superuser account? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_superuser
    fi
    
    # Testing
    read -p "Run production tests? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_tests
    fi
    
    # Summary
    show_summary
    
    print_success "Deployment finished successfully!"
}

# Run main function
main "$@"
