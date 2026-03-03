# Seed Brute-Force Tool (SBFT) v2.0.0

[![CI](https://github.com/naviNBRuas/SBFT/actions/workflows/ci.yml/badge.svg)](https://github.com/naviNBRuas/SBFT/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/sbft-academic.svg)](https://badge.fury.io/py/sbft-academic)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ⚠️ IMPORTANT DISCLAIMER

**This project is for academic and educational purposes only.** SBFT demonstrates the cryptographic security of BIP39 seed phrases through empirical computation. The probability of finding a funded wallet is infinitesimally small (approximately 1 in 2^128). 

**Key Points:**
- **NOT FOR FINANCIAL GAIN**: You are statistically more likely to be struck by lightning every day for a year than to find a funded wallet
- **EDUCATIONAL PURPOSE**: Designed to teach cryptographic security principles through hands-on experience
- **USE AT YOUR OWN RISK**: The authors are not liable for any consequences from using this tool

See [DISCLAIMER.md](DISCLAIMER.md) for full legal disclaimer.

## 🎯 Project Overview

SBFT is a highly sophisticated, production-grade brute-force engine that demonstrates why modern cryptographic systems are secure. Rather than seeking financial gain, it provides:

- **Empirical Proof**: Experience firsthand why 2^128 is computationally infeasible
- **Engineering Excellence**: Professional-grade concurrent, fault-tolerant design
- **Transparent Security**: Open implementation showing why obscurity ≠ security
- **Academic Research**: Rigorous tooling for cryptographic security studies

## 🚀 Key Features

### Performance & Scalability
- **Adaptive Batch Sizing**: Dynamically adjusts based on real-time performance
- **Multi-Provider Architecture**: Concurrent queries across multiple blockchain APIs
- **Circuit Breaker Pattern**: Automatic failover and resilience against provider outages
- **Rate Limiting**: Intelligent request throttling to respect API quotas

### Monitoring & Observability
- **Real-Time Metrics**: Continuous performance tracking and health monitoring
- **Anomaly Detection**: Automatic identification of performance degradation
- **Comprehensive Logging**: Detailed audit trails for research and debugging
- **Progress Tracking**: Accurate completion percentage and ETA calculation

### Reliability & Fault Tolerance
- **Graceful Degradation**: Continued operation despite partial provider failures
- **Checkpoint Recovery**: Persistent state management for interruption recovery
- **Error Classification**: Detailed categorization of failure modes
- **Resource Health Checks**: System monitoring for optimal operation

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   Config Layer  │───▶│  Worker Manager  │───▶│  Key Generator     │
│  (config.ini)   │    │                  │    │  (Multiprocessing) │
└─────────────────┘    └──────────────────┘    └────────────────────┘
                              │                         │
                              ▼                         ▼
                   ┌──────────────────┐    ┌────────────────────┐
                   │  Monitor System  │    │  Balance Checker   │
                   │  (Real-time)     │◀───│  (Async/Await)     │
                   └──────────────────┘    └────────────────────┘
                              │                         │
                              ▼                         ▼
                   ┌──────────────────┐    ┌────────────────────┐
                   │  State Manager   │    │  Provider Pool     │
                   │  (File Locking)  │    │  (Multi-chain)     │
                   └──────────────────┘    └────────────────────┘
```

## 📦 Installation

### Prerequisites
- Python 3.8+
- pip package manager
- Virtual environment (recommended)

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/naviNBRuas/SBFT.git
cd SBFT

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install SBFT in development mode
pip install -e .
```

### PyPI Installation

```bash
pip install sbft-academic
```

## ⚙️ Configuration

Edit `config.ini` with your settings:

```ini
[DEFAULT]
# Core Settings
DESTINATION_ADDRESS = bc1qyour_bitcoin_address_here
NETWORK = bitcoin
MINIMUM_BALANCE_SATS = 1000

# Providers (comma-separated)
PROVIDERS = blockcypher,blockstream,alchemy

# API Keys (optional but recommended)
BLOCKCYPHER_TOKEN = your_token_here
ALCHEMY_API_KEY = your_key_here

# Performance Tuning
MAX_WORKERS = 8
BATCH_SIZE = 100
CHUNK_SIZE = 1000000

# Monitoring
ENABLE_MONITORING = true
LOG_LEVEL = INFO
```

## ▶️ Usage

### Basic Execution

```bash
# Run the tool
python -m sbft.main

# Or if installed as package
sbft
```

### Multiple Instances

You can run multiple instances safely - they coordinate via file locking:

```bash
# Terminal 1
python -m sbft.main

# Terminal 2 (different machine or process)
python -m sbft.main
```

## 📊 Monitoring & Metrics

SBFT provides comprehensive monitoring capabilities:

### Real-time Dashboard
- Keys processed per second
- Provider success/failure rates
- Memory and CPU usage
- Network request statistics

### Performance Metrics
- Adaptive batch sizing recommendations
- Provider health scores
- Anomaly detection alerts
- Resource utilization graphs

### Log Files
- `sbft.log`: Main application logs
- `metrics.json`: Periodic performance snapshots
- `failed_batches.log`: Records of failed API requests
- `hits.txt`: Any discovered funded wallets

## 🔌 Provider Integration

### Supported Networks
- **Bitcoin**: BlockCypher, Blockstream.info
- **Ethereum**: Alchemy, Infura
- **Polygon**: Alchemy, Infura
- **Arbitrum**: Alchemy, Infura
- **Optimism**: Alchemy, Infura

### Adding New Providers

Create a new provider by extending `ProviderBase`:

```python
from sbft.sbft_providers import ProviderBase

class CustomProvider(ProviderBase):
    @property
    def name(self) -> str:
        return "custom"
    
    @property
    def base_url(self) -> str:
        return "https://api.custom.com"
    
    async def get_balances(self, addresses: List[str]) -> Dict[str, int]:
        # Implement balance checking logic
        pass
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/test_basic_functionality.py
pytest tests/test_async_providers.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/
```

## 🛠️ Development

### Code Quality
The project includes automated code quality checks:

```bash
# Run linters
black src/ tests/
flake8 src/ tests/

# Run security scans
bandit -r src/
safety check

# Run type checking
mypy src/
```

### CI/CD Pipeline
GitHub Actions automatically runs:
- Tests across multiple Python versions (3.8-3.12)
- Code style and quality checks
- Security scanning
- Package building and validation

## 📚 Academic Resources

### Research Applications
SBFT is designed for academic research in:
- Cryptographic security analysis
- Brute-force resistance studies
- Blockchain API performance evaluation
- Distributed computing systems

### Related Research Areas
- Probability theory and combinatorics
- Computational complexity analysis
- Cryptographic hash function properties
- Statistical significance in large-scale computations

## 🤝 Contributing

We welcome contributions that enhance SBFT's educational value:

### Areas for Improvement
- Additional blockchain integrations
- Enhanced monitoring dashboards
- Performance optimization techniques
- Documentation improvements
- Test suite expansion

### Development Setup

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest tests/

# Code formatting
black src/
flake8 src/
```

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 👤 Author

**Navin B. Ruas**  
NBR. Company LTD  
📧 founder@nbr.company  
🌐 https://nbr.company

## ⭐ Support

If you find this project educational or interesting, please consider:

- Starring the repository
- Sharing with colleagues and students
- Contributing improvements
- Citing in academic work

---

*"The ultimate measure of security is not how strong your cryptography is, but how difficult it makes the attacker's job."*