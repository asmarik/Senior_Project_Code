document.addEventListener('DOMContentLoaded', () => {
    uiManager.init();

    const heroSection = document.getElementById('heroSection');
    if (heroSection) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 100) {
                heroSection.style.opacity = '0';
                heroSection.style.pointerEvents = 'none';
            } else {
                heroSection.style.opacity = '1';
                heroSection.style.pointerEvents = 'auto';
            }
        });
    }
});

function clearFile() {
    uiManager.clearFile();
}

function proceedToAnalysis() {
    uiManager.navigateToStep('analysis');
}

function resetAnalysis() {
    uiManager.navigateToStep('upload');
}

function showHelp() {
    document.getElementById('helpModal').classList.add('active');
}

function closeHelp() {
    document.getElementById('helpModal').classList.remove('active');
}

function startAnalysis() {
    const uploadStep = document.querySelector('[data-step="upload"]');
    if (uploadStep) {
        uploadStep.click();
    }

    const heroSection = document.getElementById('heroSection');
    if (heroSection) {
        heroSection.style.display = 'none';
    }
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
}

function showDemo() {
    uiManager.showError('Demo feature coming soon!');
}

function toggleAccordion(headerEl) {
    const content = headerEl.nextElementSibling;
    headerEl.classList.toggle('active');
    content.classList.toggle('active');
}

async function handleAPICall(methodCardId, apiFunction, resultTitle, renderFunction) {
    if (!apiClient.getFile()) {
        uiManager.showError('Please upload a document first.');
        return;
    }

    const methodCard = document.querySelector(`#${methodCardId}`).closest('.method-card');
    uiManager.showMethodLoading(methodCard, true);
    uiManager.hideError();

    try {
        const data = await apiFunction();
        uiManager.showMethodLoading(methodCard, false);

        const content = renderFunction(data);
        uiManager.showResults(resultTitle, content);
    } catch (error) {
        uiManager.showMethodLoading(methodCard, false);
        uiManager.showError(`Error: ${error.message}`);
    }
}

async function runTestOCR() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'testOCR',
        () => apiClient.testOCR(),
        'OCR Extraction Results',
        (data) => resultsRenderer.renderTest(data, 'ocr')
    );
}

async function runTestHybrid() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'testHybrid',
        () => apiClient.testHybrid(),
        'Hybrid Search Results',
        (data) => resultsRenderer.renderTest(data, 'hybrid')
    );
}

async function runTestRAG() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'testRAG',
        () => apiClient.testRAG(),
        'RAG Analysis Results',
        (data) => resultsRenderer.renderTest(data, 'rag')
    );
}

async function runScore() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'score',
        () => apiClient.getScore(),
        'Compliance Score Assessment',
        (data) => resultsRenderer.renderScore(data)
    );
}

async function runScoreLLM() {
    const btn = event.target.closest('button');
    const methodCard = btn.closest('.method-card');
    const loading = methodCard.querySelector('.loading-text');
    const originalText = loading.textContent;

    loading.textContent = 'Running deep LLM analysis... This may take 30-60 seconds.';

    await handleAPICall(
        btn.id || 'scoreLLM',
        () => apiClient.getScoreLLM(),
        'Recommendation Analysis Assessment',
        (data) => resultsRenderer.renderScore(data)
    );

    loading.textContent = originalText;
}

async function runMissing() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'missing',
        () => apiClient.getMissing(),
        'Gap Analysis Results',
        (data) => resultsRenderer.renderMissing(data)
    );
}

async function runMissingLLM() {
    const btn = event.target.closest('button');
    const methodCard = btn.closest('.method-card');
    const loading = methodCard.querySelector('.loading-text');
    const originalText = loading.textContent;

    loading.textContent = 'Running detailed LLM gap analysis... This may take 30-60 seconds.';

    await handleAPICall(
        btn.id || 'missingLLM',
        () => apiClient.getMissingLLM(),
        'LLM Gap Analysis Results',
        (data) => resultsRenderer.renderMissing(data)
    );

    loading.textContent = originalText;
}

async function runUpload() {
    const btn = event.target.closest('button');
    await handleAPICall(
        btn.id || 'upload',
        () => apiClient.uploadFile(),
        'Comprehensive Analysis Results',
        (data) => resultsRenderer.renderUpload(data)
    );
}
