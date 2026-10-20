# MVP acceptance criteria

The first MVP is a manual-input, model-aware application shell. It is not required to make numerical forecasts before an eligible baseline/model and labelled dataset exist. No mock probability can be presented as a real forecast.

## Entry form
- [ ] Train number, journey date, boarding station and destination are collected.
- [ ] Class and quota can be selected or explicitly marked unknown where the design allows it.
- [ ] User can add/remove multiple passenger rows.
- [ ] Original and latest observed status remain distinct.
- [ ] Status position and status category are validated separately.
- [ ] Observation timestamp is recorded or identified as unknown.
- [ ] Passenger names are not required.
- [ ] Validation errors identify how to correct the request.

## Prediction result contract
- [ ] API indicates model/baseline/unavailable state.
- [ ] Numeric results appear only for validated coverage.
- [ ] Result identifies target moment and prediction timestamp.
- [ ] Every model estimate contains model/version and evidence metadata.
- [ ] CNF and RAC are worded distinctly.
- [ ] Passenger probabilities are coherent with the documented outcome set.
- [ ] Group-level results come from a joint or validated structured estimate.
- [ ] Unsupported cases show a useful abstention message.

## Data and privacy
- [ ] Synthetic UI fixtures are labelled and isolated from empirical training/evaluation.
- [ ] No real PNR or passenger information is committed.
- [ ] Raw PNRs are not exposed in browser URLs or application logs.
- [ ] Data source permission and retention decisions are documented before tracking.
- [ ] Live lookup is disabled when no approved provider is configured.

## Engineering and research
- [ ] Domain normalization has unit tests, including unknown status behavior.
- [ ] API validation and error cases have tests.
- [ ] Prediction logic can be tested without a live railway API.
- [ ] A baseline is evaluated chronologically before ML performance is claimed.
- [ ] Tests document the difference between product behavior and research evidence.
- [ ] README/project status describes what actually works.

## Release decision

The MVP may be demonstrated as a manual-input workflow before a trained model exists only if numeric forecast output is clearly unavailable or labelled as illustrative test data. It cannot be promoted as a validated confirmation predictor until the data and model evaluation gates are passed.
