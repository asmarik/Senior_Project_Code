document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const fileUploadArea = document.getElementById('fileUploadArea');

    fileUploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUploadArea.classList.add('dragover');
    });

    fileUploadArea.addEventListener('dragleave', () => {
        fileUploadArea.classList.remove('dragover');
    });

    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.classList.remove('dragover');

        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            fileInput.files = e.dataTransfer.files;
            handleFileSelect(file);
        }
    });

    function handleFileSelect(file) {
        if (file.type !== 'application/pdf') {
            uiManager.showError('Please select a PDF file.');
            return;
        }

        if (file.size > 16 * 1024 * 1024) {
            uiManager.showError('File size must be less than 16MB.');
            return;
        }

        apiClient.setFile(file);
        uiManager.updateFileInfo(file);
        uiManager.enableAllButtons();
    }

    document.getElementById('closeResultsBtn').addEventListener('click', () => {
        uiManager.closeResults();
    });
});

async function handleAPICall(sectionId, apiFunction, resultTitle, resultRenderer) {
    if (!apiClient.getFile()) {
        uiManager.showError('Please select a PDF file first.');
        return;
    }

    uiManager.showLoading(sectionId, 'Processing your request...');
    uiManager.hideError();

    try {
        const data = await apiFunction();
        uiManager.hideLoading(sectionId);

        const content = resultRenderer(data);
        uiManager.showResults(resultTitle, content);
    } catch (error) {
        uiManager.hideLoading(sectionId);
        uiManager.showError(`Error: ${error.message}`);
    }
}

async function runTestOCR() {
    await handleAPICall(
        'testingSection',
        () => apiClient.testOCR(),
        'OCR Test Results',
        (data) => uiManager.createTestDisplay(data, 'ocr')
    );
}

async function runTestHybrid() {
    await handleAPICall(
        'testingSection',
        () => apiClient.testHybrid(),
        'Hybrid Search Test Results',
        (data) => uiManager.createTestDisplay(data, 'hybrid')
    );
}

async function runTestRAG() {
    await handleAPICall(
        'testingSection',
        () => apiClient.testRAG(),
        'RAG Test Results',
        (data) => uiManager.createTestDisplay(data, 'rag')
    );
}

async function runScore() {
    await handleAPICall(
        'scoringSection',
        () => apiClient.getScore(),
        'Compliance Score',
        (data) => uiManager.createScoreDisplay(data)
    );
}

async function runScoreLLM() {
    uiManager.showLoading('scoringSection', 'Running LLM analysis... This may take up to 2 minutes.');

    if (!apiClient.getFile()) {
        uiManager.hideLoading('scoringSection');
        uiManager.showError('Please select a PDF file first.');
        return;
    }

    uiManager.hideError();

    try {
        const data = await apiClient.getScoreLLM();
        uiManager.hideLoading('scoringSection');

        const content = uiManager.createScoreDisplay(data);
        uiManager.showResults('Recommendation Analysis', content);
    } catch (error) {
        uiManager.hideLoading('scoringSection');
        uiManager.showError(`Error: ${error.message}`);
    }
}

async function runMissing() {
    await handleAPICall(
        'missingSection',
        () => apiClient.getMissing(),
        'Missing Articles Analysis',
        (data) => uiManager.createMissingDisplay(data)
    );
}

async function runMissingLLM() {
    uiManager.showLoading('missingSection', 'Running LLM analysis... This may take up to 2 minutes.');

    if (!apiClient.getFile()) {
        uiManager.hideLoading('missingSection');
        uiManager.showError('Please select a PDF file first.');
        return;
    }

    uiManager.hideError();

    try {
        const data = await apiClient.getMissingLLM();
        uiManager.hideLoading('missingSection');

        const content = uiManager.createMissingDisplay(data);
        uiManager.showResults('LLM Missing Articles Analysis', content);
    } catch (error) {
        uiManager.hideLoading('missingSection');
        uiManager.showError(`Error: ${error.message}`);
    }
}

async function runUpload() {
    await handleAPICall(
        'uploadSection',
        () => apiClient.uploadFile(),
        'Upload Results',
        (data) => uiManager.createUploadDisplay(data)
    );
}
