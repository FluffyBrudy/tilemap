#!/bin/bash
# Build script for Tilemap Editor
# This script helps automate the PyInstaller build process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SPEC_FILE="tilemap_editor.spec"
DIST_DIR="dist"
BUILD_DIR="build"
VENV_PATH_ROOT="venv"
VENV_PATH_SRC="src/venv"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect Python to use
detect_python() {
    # Check if venv is activated
    if [ -n "$VIRTUAL_ENV" ]; then
        PYTHON_CMD="python"
        print_info "Using activated virtual environment: $VIRTUAL_ENV"
        return 0
    fi
    
    # Check if local venv exists in project root
    if [ -d "$VENV_PATH_ROOT" ]; then
        print_info "Found venv at $VENV_PATH_ROOT, activating..."
        source "$VENV_PATH_ROOT/bin/activate"
        PYTHON_CMD="python"
        print_success "Using venv Python"
        return 0
    fi
    
    # Check if local venv exists in src directory
    if [ -d "$VENV_PATH_SRC" ]; then
        print_info "Found venv at $VENV_PATH_SRC, activating..."
        source "$VENV_PATH_SRC/bin/activate"
        PYTHON_CMD="python"
        print_success "Using venv Python"
        return 0
    fi
    
    # Fall back to system python3
    PYTHON_CMD="python3"
    print_warning "No virtual environment detected, using system Python"
    print_warning "For better dependency isolation, consider creating a venv:"
    print_warning "  python3.12 -m venv venv"
    print_warning "  source venv/bin/activate.fish  # or .bash"
    print_warning "  pip install pyinstaller pygame"
    return 0
}

# Parse command line arguments
CLEAN=false
DEBUG=false
ONEFILE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --onefile)
            ONEFILE=true
            shift
            ;;
        --help)
            echo "Usage: ./build.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean     Clean build artifacts before building"
            echo "  --debug     Build with console window for debugging"
            echo "  --onefile   Build as a single executable file"
            echo "  --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./build.sh                    # Normal build"
            echo "  ./build.sh --clean            # Clean build"
            echo "  ./build.sh --debug            # Build with console"
            echo "  ./build.sh --clean --onefile  # Clean single-file build"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print banner
echo ""
echo "╔════════════════════════════════════════╗"
echo "║    Tilemap Editor - Build Script      ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if spec file exists
if [ ! -f "$SPEC_FILE" ]; then
    print_error "Spec file '$SPEC_FILE' not found!"
    exit 1
fi

# Clean build artifacts if requested
if [ "$CLEAN" = true ]; then
    print_info "Cleaning build artifacts..."
    if [ -d "$DIST_DIR" ]; then
        rm -rf "$DIST_DIR"
        print_success "Removed $DIST_DIR/"
    fi
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        print_success "Removed $BUILD_DIR/"
    fi
    echo ""
fi

# Modify spec file based on options
if [ "$DEBUG" = true ]; then
    print_info "Debug mode enabled (console window will be shown)"
    # Temporarily modify spec file to enable console
    sed -i.bak 's/CONSOLE_MODE = False/CONSOLE_MODE = True/' "$SPEC_FILE"
fi

if [ "$ONEFILE" = true ]; then
    print_info "Single-file mode enabled"
    sed -i.bak 's/ONE_FILE = False/ONE_FILE = True/' "$SPEC_FILE"
fi

# Detect and setup Python environment
detect_python

# Run PyInstaller
print_info "Building with PyInstaller..."
print_info "Using Python: $($PYTHON_CMD --version)"
echo ""

if $PYTHON_CMD -m PyInstaller "$SPEC_FILE"; then
    echo ""
    print_success "Build completed successfully! 🎉"
    echo ""
    print_info "Output location: $DIST_DIR/TilemapEditor/"
    
    # Calculate build size
    if [ -d "$DIST_DIR/TilemapEditor" ]; then
        SIZE=$(du -sh "$DIST_DIR/TilemapEditor" | cut -f1)
        print_info "Build size: $SIZE"
    fi
    
    echo ""
    print_info "To run the application:"
    echo "  cd $DIST_DIR/TilemapEditor"
    echo "  ./TilemapEditor"
    echo ""
else
    echo ""
    print_error "Build failed!"
    exit 1
fi

# Restore spec file if modified
if [ "$DEBUG" = true ] || [ "$ONEFILE" = true ]; then
    if [ -f "${SPEC_FILE}.bak" ]; then
        mv "${SPEC_FILE}.bak" "$SPEC_FILE"
        print_info "Restored original spec file"
    fi
fi

print_success "All done!"
