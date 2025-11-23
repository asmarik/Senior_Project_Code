class UIManager {
    constructor() {
        this.currentStep = 'upload';
        this.currentFile = null;
    }

    init() {
        this.setupFileUpload();
        this.setupNavigation();
    }

    setupFileUpload() {
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        const filePreview = document.getElementById('filePreview');

        uploadZone.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files[0]);
            }
        });

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');

            if (e.dataTransfer.files.length > 0) {
                this.handleFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    handleFileSelect(file) {
        if (file.type !== 'application/pdf') {
            this.showError('Please select a PDF file.');
            return;
        }

        if (file.size > 16 * 1024 * 1024) {
            this.showError('File size must be less than 16MB.');
            return;
        }

        this.currentFile = file;
        apiClient.setFile(file);

        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = this.formatFileSize(file.size);
        document.getElementById('filePreview').classList.add('active');
        document.getElementById('uploadZone').style.display = 'none';
        document.getElementById('proceedBtn').disabled = false;

        this.enableAnalysisButtons();
    }

    clearFile() {
        this.currentFile = null;
        apiClient.setFile(null);

        document.getElementById('filePreview').classList.remove('active');
        document.getElementById('uploadZone').style.display = 'block';
        document.getElementById('proceedBtn').disabled = true;

        this.disableAnalysisButtons();
    }

    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const step = item.dataset.step;
                this.navigateToStep(step);
            });
        });
    }

    navigateToStep(step) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        document.querySelector(`[data-step="${step}"]`).classList.add('active');
        document.getElementById(`${step}Step`).classList.add('active');

        this.currentStep = step;
    }

    enableAnalysisButtons() {
        document.querySelectorAll('[data-requires-file]').forEach(btn => {
            btn.disabled = false;
        });
    }

    disableAnalysisButtons() {
        document.querySelectorAll('[data-requires-file]').forEach(btn => {
            btn.disabled = true;
        });
    }

    showMethodLoading(methodCard, show = true) {
        const loading = methodCard.querySelector('.method-loading');
        const actions = methodCard.querySelector('.method-actions');

        if (show) {
            loading.classList.add('active');
            actions.style.display = 'none';
        } else {
            loading.classList.remove('active');
            actions.style.display = 'flex';
        }
    }

    showError(message) {
        const errorEl = document.getElementById('globalError');
        errorEl.textContent = message;
        errorEl.classList.add('active');

        setTimeout(() => {
            errorEl.classList.remove('active');
        }, 5000);
    }

    hideError() {
        const errorEl = document.getElementById('globalError');
        errorEl.classList.remove('active');
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }

    showResults(title, content) {
        document.getElementById('resultsTitle').textContent = title;
        document.getElementById('resultsContent').innerHTML = content;
        this.navigateToStep('results');

        setTimeout(() => {
            this.animateProgressBars();
        }, 100);
    }

    animateProgressBars() {
        const progressBars = document.querySelectorAll('.coverage-progress-bar');
        progressBars.forEach(bar => {
            const width = bar.getAttribute('data-width');
            if (width) {
                setTimeout(() => {
                    bar.style.width = width + '%';
                }, 100);
            }
        });
    }
}

const uiManager = new UIManager();
