# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-12-12

### 🚀 Major Features

#### Priority Connection Management
- **Intelligent Failover**: Implement priority-based RPC endpoint selection with smart failover
- **Health Monitoring**: Add comprehensive endpoint health tracking with automatic recovery
- **User Configuration**: Preserve user-configured RPC URL priorities throughout the system
- **Exponential Backoff**: Implement smart cooling periods for failed endpoints
- **Web3 Instance Caching**: Optimize performance with intelligent instance reuse

#### Address Checksum Management
- **System-wide Standardization**: Implement comprehensive address checksum management
- **Boundary Validation**: Convert addresses to checksum format at system entry points
- **Internal Consistency**: Ensure checksum format preservation throughout the lifecycle
- **Error Elimination**: Completely resolve Web3.py checksum address validation errors

#### Architecture Refactoring
- **Modular Core Design**: Refactor to clean separation of concerns with registry pattern
- **Stateless Optimization**: Remove unnecessary connection management for HTTP RPC adapters
- **Task-based State Management**: Implement async task-based state tracking instead of manual flags
- **Enhanced Testing**: Comprehensive test suite with 95%+ coverage

### 🛠️ Technical Improvements

#### Core Components
- **PriorityConnectionPool**: Smart endpoint selection with configurable retry logic
- **EthereumAdapter**: Priority-based routing with rate limiting and error handling
- **CallbackRegistry**: Enhanced address management with checksum preservation
- **AdapterRegistry**: Centralized adapter lifecycle management
- **EventProcessor**: Streamlined event processing pipeline

#### Configuration System
- **Enhanced Validation**: Improved configuration validation with checksum conversion
- **Priority Preservation**: Complete preservation of user RPC endpoint priorities
- **Convention over Configuration**: Simplified configuration with intelligent defaults
- **Type Safety**: Comprehensive type hints with Pydantic integration

### 📦 Package Structure
- **Modular Utils**: Organized utility functions into specialized modules
- **Comprehensive Examples**: Added complete usage examples and documentation
- **API Documentation**: Enhanced docstrings with Google-style formatting
- **Development Tools**: Improved development workflow with pre-commit hooks

### 🐛 Bug Fixes
- **Address Format Issues**: Completely resolve Web3.py checksum address validation errors
- **Connection Management**: Fix unnecessary connection state management for HTTP RPC
- **Priority Information Loss**: Preserve user configuration priorities throughout the system
- **Memory Leaks**: Fix Web3 instance caching and cleanup issues
- **Error Handling**: Improve error propagation and context preservation

### ⚡ Performance Improvements
- **Reduced Latency**: Priority-based endpoint selection reduces response time
- **Connection Reuse**: Web3 instance caching minimizes connection overhead
- **Smart Retry Logic**: Intelligent failover reduces unnecessary requests
- **Memory Optimization**: Improved memory management with proper cleanup

### 🔒 Security Enhancements
- **Input Validation**: Comprehensive validation of all external inputs
- **Address Security**: Automatic checksum conversion prevents address manipulation
- **Error Disclosure**: Improved error messages without sensitive information exposure
- **Dependency Security**: Updated dependencies with security patches

### 📚 Documentation
- **Quick Start Guide**: Comprehensive getting started documentation
- **API Reference**: Complete API documentation with examples
- **Architecture Guide**: Detailed technical architecture documentation
- **Best Practices**: Production deployment and optimization guidelines

### 🧪 Testing
- **Unit Tests**: 220+ unit tests with comprehensive edge case coverage
- **Integration Tests**: End-to-end workflow validation
- **Performance Tests**: Load testing and benchmarking suite
- **Type Checking**: MyPy configuration with strict type checking

## [0.1.0] - 2024-11-15

### 🎉 Initial Release
- **Multi-chain Support**: Basic support for Ethereum and other EVM chains
- **Event Listening**: Core blockchain event monitoring functionality
- **Configuration System**: Flexible YAML and programmatic configuration
- **Basic Adapters**: Foundation adapter architecture
- **Documentation**: Initial project documentation

---

## Migration Guide

### From 0.1.0 to 0.2.0

#### Configuration Changes
```yaml
# Old format (still supported)
chains:
  ethereum:
    rpc_urls:
      - url: "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
      - url: "https://backup-rpc.com"
    chain_type: "ethereum"

# New format with priority support (recommended)
chains:
  ethereum:
    rpc_urls:
      - url: "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
        priority: 1  # Higher priority
      - url: "https://backup-rpc.com"
        priority: 2  # Lower priority
    chain_type: "ethereum"
```

#### API Changes
```python
# Address handling is now automatic
listener.on_event(
    "ethereum",
    "0xa0b86a33e6441e1ca48558572a901d6885543326",  # Any format accepted
    "Transfer",
    callback_function
)
# Addresses are automatically converted to checksum format internally
```

#### Breaking Changes
- **Internal API Changes**: Some internal APIs have changed for better architecture
- **Configuration Schema**: Enhanced configuration with new priority options
- **Test Suite**: Restructured tests for better coverage and maintainability

#### New Features
- **Priority Connection Management**: Automatic failover with user-defined priorities
- **Address Checksum Management**: Automatic address format standardization
- **Enhanced Error Handling**: Better error messages and recovery mechanisms
- **Performance Optimizations**: Faster response times and reduced resource usage

---

## Support

- **Documentation**: https://chain-listener.readthedocs.io
- **Issues**: https://github.com/chain-listener/chain-listener/issues
- **Discussions**: https://github.com/chain-listener/chain-listener/discussions
- **Security**: security@chainlistener.dev

---

*This changelog follows the principles of [Keep a Changelog](https://keepachangelog.com/).*