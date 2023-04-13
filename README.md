# FELT Flow - FELT Labs command line too
Running federated learning via python

## Installation 
First you have to install this python package:
```
pip install feltflow
```

Then you have to setup following environment variables:
```bash
export WEB3_INFURA_PROJECT_ID="a0b1..."
export PRIVATE_KEY="0xa0b1..."
```

After that you should be ready for running FELT Flow.

## Examples
Example command line for running FELT Flow:
```
felt-flow --chain_id 80001 \
   --name "Training name" \
   --dids 'did:op:3632e8584837f2eac04d85466c0cebd8b8cb2673b472a82a310175da9730042a,did:op:cad4a81c9a8e1c1071ccf3e9dea6f8f42d58e100fa3ddf2950c8f0da9e0dda46' \
   --algo_config '{"id":"FELT","name":"FELT Federated Training","assets":{"training":"did:op:87e58362dfc60bbeaf83d5495e587a891a9ca697a6c5ec3585bfe1f8586f85fa","aggregation":"did:op:dcefb784c302094251ae1bc19d898eb584bd7be20a623bab078d4df0283e6c79","emptyDataset":"did:op:20bf68f480e17aff3e6947792e75b615908a46394ba33c8cfb94587a0a8d2c29"},"hasParameters":true}' \
   --algocustomdata '{"model_definition":{"model_name":"LinearRegression","model_type":"sklearn"},"data_type":"csv","target_column":-1}' \
   --session <exported_session_cookie> \
   --api_endpoint "https://app.feltlabs.ai"
```


## Development
### Install
```
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
```

### Test
```
pytest --cov=feltflow --cov-report=term
```

### Versioning
Do following steps when updating to new version:

1. Update version number in [`setup.py`](./setup.py)
2. Run following commands (replace `0.0.0` with correct version number):
   ```
   git add -A
   git commit -m "New version 0.0.0"
   git tag v0.0.0
   git push origin v0.0.0
   ```
3. Create new release on Github based on tag