# Mapping WordPress post_name -> (section, new slug, language, categories)
# section: research | notes | blog
POSTS = {
    # --- research ---------------------------------------------------------
    "hello-world": ("research", "univariate-volatility-modelling", "en", ["Econometrics", "Volatility"]),
    "7": ("research", "stochastic-portfolio-dynamics", "en", ["Portfolio Optimization", "Stochastic Processes"]),
    "time-series-analysis": ("research", "time-series-analysis", "en", ["Econometrics", "Time Series"]),
    "stylized-facts-in-financial-returns": ("research", "stylized-facts-financial-returns", "en", ["Econometrics", "Statistical Arbitrage"]),
    "multivariate-time-series-models": ("research", "multivariate-time-series-models", "en", ["Econometrics", "Time Series"]),
    "forecasting-bitcoin-price-using-deep-neural-networks": ("research", "btc-forecasting-deep-neural-networks", "en", ["Machine Learning", "Crypto"]),
    "long-short-term-memory-garch-a-hybrid-econometric-machine-learning-approach-on-bitcoin": ("research", "lstm-garch-bitcoin", "en", ["Volatility", "Machine Learning", "Crypto"]),
    "dynamic-regime-switching-garch-lstm-frameworkfor-cryptocurrency-risk-management": ("research", "rs-garch-lstm-crypto-risk", "en", ["Volatility", "Machine Learning", "Crypto"]),
    "analisi-multidimensionale-dei-regimi-finanziari": ("research", "regimi-finanziari-multidimensionali", "it", ["Financial Mathematics"]),
    "application-of-state-space-models-on-statistical-arbitragre-trading-strategies": ("research", "state-space-stat-arb", "en", ["Statistical Arbitrage", "Time Series"]),
    "from-tweet-classification-to-trading-signals-nlp-applied-to-alghorithmic-trading": ("research", "nlp-tweet-trading-signals", "en", ["Machine Learning", "NLP", "Trading"]),
    "wavelet-based-signal-extraction-and-regime-detection-in-commodity-futures": ("research", "wavelet-commodity-futures", "en", ["Signal Processing", "Commodities", "Trading"]),
    "statistical-arbitrage-in-higher-dimensions-an-integrated-kf-hmm-garch-framework-for-dynamic-multi-asset-trading": ("research", "kf-hmm-garch-stat-arb", "en", ["Statistical Arbitrage", "Volatility"]),
    # --- notes ------------------------------------------------------------
    "introduzione-alla-matematica-finanziaria": ("notes", "introduzione-matematica-finanziaria", "it", ["Financial Mathematics"]),
    "the-math-behind-the-trillion-dollar-equation-the-black-scholes-pde": ("notes", "black-scholes-pde", "en", ["Financial Mathematics", "Stochastic Calculus"]),
    "from-the-heat-equation-to-the-black-scholes": ("notes", "heat-equation-black-scholes", "en", ["Financial Mathematics", "PDE"]),
    "probabilita-discreta": ("notes", "probabilita-discreta", "it", ["Probability"]),
    "assiomi-della-probabilita": ("notes", "assiomi-probabilita", "it", ["Probability", "Measure Theory"]),
    "variabili-aleatorie-su-uno-spazio-numerabile": ("notes", "variabili-aleatorie-spazio-numerabile", "it", ["Probability"]),
    "costruzione-di-una-misura-di-probabilita": ("notes", "costruzione-misura-probabilita", "it", ["Measure Theory"]),
    "il-ruolo-dellintegrale-di-lebesgue-in-probabilita": ("notes", "integrale-lebesgue-probabilita", "it", ["Measure Theory"]),
    "variabili-aleatorie-indipendenti": ("notes", "variabili-aleatorie-indipendenti", "it", ["Probability"]),
    "distribuzioni-di-probabilita-su-%e2%84%9d": ("notes", "distribuzioni-probabilita-r", "it", ["Probability"]),
    "distribuzioni-di-probabilita-su-%e2%84%9d%e2%81%bf": ("notes", "distribuzioni-probabilita-rn", "it", ["Probability"]),
    "trasformata-di-fourier-e-funzioni-caratteristiche": ("notes", "fourier-funzioni-caratteristiche", "it", ["Probability", "Fourier Analysis"]),
    "geometria-del-valore-atteso-condizionato-spazi-di-hilbert-spazidi-banach-e-spazi-lp": ("notes", "geometria-valore-atteso-condizionato", "it", ["Probability", "Functional Analysis"]),
    "appunti-di-probabilita-e-teoria-della-misura": ("notes", "appunti-probabilita-teoria-misura", "it", ["Probability", "Measure Theory"]),
    "appunti-di-algebra-lineare-ed-equazioni-differenziali": ("notes", "appunti-algebra-lineare-equazioni-differenziali", "it", ["Linear Algebra", "Differential Equations"]),
    "dalle-time-series-alla-wavelet-guida-intuitiva": ("notes", "time-series-wavelet-guida", "it", ["Signal Processing", "Time Series"]),
    # --- blog -------------------------------------------------------------
    "this-is-the-closest-youll-get-to-visualize-a-%cf%83-algebra": ("blog", "visualizing-sigma-algebra", "en", ["Measure Theory"]),
    "overcoming-excels-lookup-limitations-using-the-levenshtein-algorithm": ("blog", "excel-levenshtein-lookup", "en", ["Excel", "VBA"]),
}
