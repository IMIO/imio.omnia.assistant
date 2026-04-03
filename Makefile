JS_SRC = src/imio/omnia/assistant/browser/resources
STATIC  = src/imio/omnia/assistant/browser/static

.PHONY: build-js clean-js

build-js:
	cd $(JS_SRC) && npm ci && npm run build
	cp $(JS_SRC)/dist/omnia-assistant-ui.umd.cjs  $(STATIC)/omnia-assistant-ui.js
	cp $(JS_SRC)/dist/omnia-assistant-ui.css       $(STATIC)/omnia-assistant-ui.css
	cp $(JS_SRC)/node_modules/preact/dist/preact.umd.js $(STATIC)/preact.umd.js

clean-js:
	rm -f $(STATIC)/omnia-assistant-ui.js $(STATIC)/omnia-assistant-ui.css $(STATIC)/preact.umd.js
