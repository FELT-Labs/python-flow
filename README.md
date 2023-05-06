# FELT Flow - FELT Labs command line too
Running federated learning via python

## Installation 
### 1. Install Package
First you have to install this python package:
```bash
git clone https://github.com/FELT-Labs/python-flow.git
cd python-flow
pip install .
```

### 2. Environment variables
You can rename `.env.example` file in `python-flow` directory to `.env` and place correct values for following variables:
```bash
export WEB3_INFURA_PROJECT_ID="a0b1..."
export PRIVATE_KEY="0xa0b1..."
```
Alternatively you can export those variables directly in your terminal or place these exports into `.bashrc` file.

- `WEB3_INFURA_PROJECT_ID` can be obtained from [infura.io](https://www.infura.io) and is used for accessing nodes on blockchain
- `PRIVATE_KEY` is private key of your blockchain account which will be used for signing the transaction (purchasing data and ordering training)


After that you should be ready for running FELT Flow.

## Examples
Example command line for running FELT Flow:
```bash
felt-flow --launch_token <launch_token_from_feltlabs_app>
```
This token is obtained through our web application: [app.feltlabs.ai](https://app.feltlabs.ai).


## Development
### Install
```bash
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
```

### Test
```bash
pytest --cov=feltflow --cov-report=term
```

### Versioning
Do following steps when updating to new version:

1. Update version number in [`setup.py`](./setup.py)
2. Run following commands (replace `0.0.0` with correct version number):
   ```bash
   git add -A
   git commit -m "New version 0.0.0"
   git tag v0.0.0
   git push origin v0.0.0
   ```
3. Create new release on Github based on tag

## Potential issues
### Error while running `pip install .`
There might be some issues with installing `ocean-lib` package. Mainly on mac M1 problems with installing `wheel` or `coincurve`
Workaround is explained here https://github.com/oceanprotocol/ocean.py/blob/main/READMEs/install.md
