JS_SRC = src/imio/omnia/assistant/browser/resources
STATIC  = src/imio/omnia/assistant/browser/static
NPM_DIST = $(JS_SRC)/node_modules/@imiobe/omnia-assistant-ui/dist

.PHONY: build-js clean-js

build-js:
	cd $(JS_SRC) && npm ci
	cp $(NPM_DIST)/omnia-assistant-ui.umd.cjs $(STATIC)/omnia-assistant-ui.js

clean-js:
	rm -f $(STATIC)/omnia-assistant-ui.js
