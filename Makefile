PY := PYTHONPATH=src:scripts python3

.PHONY: ops pricing causal sensing gate heldout report test lint web

ops:       ## forecasts and operations policies on the dev city (about 6 min)
	$(PY) scripts/ops_eval.py dev
pricing:   ## experiment designs, elasticity switchback and price policy (about 5 min)
	cd scripts && PYTHONPATH=../src:. python3 pricing_eval.py dev
causal:    ## difference in differences for the competitor launch
	cd scripts && PYTHONPATH=../src:. python3 causal_eval.py
sensing:   ## train and score the IMU riding-safety model, export int8 ONNX (about 3 min)
	$(PY) scripts/sensing_eval.py dev
gate:      ## release decisions from the dev reports
	$(PY) scripts/gate.py
heldout:   ## the held-out city and scooter generation, once
	cd scripts && PYTHONPATH=../src:. python3 heldout.py
report:    ## dashboard data and README tables
	$(PY) scripts/report.py
test:
	python3 -m pytest -q
lint:
	ruff check src scripts tests
web:
	cd web && npm ci && npm test && npm run build
