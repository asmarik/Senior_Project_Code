// State Management
const appState = {
    currentView: 'dashboard',
    uploadedFile: null,
    selectedMethod: null, // 'score' or 'score-llm'
    darkMode: localStorage.getItem('darkMode') === 'true',
    results: null,
    fileSignature: null,
    serverUploadSignature: null
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeDarkMode();
    initializeNavigation();
    // Initialize breadcrumb to current view
    updateBreadcrumb(appState.currentView);
    initializeFileUpload();
    updateDashboardKPIs();
});

// Dark Mode
function initializeDarkMode() {
    if (appState.darkMode) {
        document.documentElement.classList.add('dark');
    }
}

function toggleDarkMode() {
    appState.darkMode = !appState.darkMode;
    localStorage.setItem('darkMode', appState.darkMode);

    if (appState.darkMode) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

// Navigation
function initializeNavigation() {
    document.querySelectorAll('[data-view]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const view = btn.getAttribute('data-view');
            navigateToView(view);
        });
    });
}

function navigateToView(viewName) {
    appState.currentView = viewName;

    // Update active nav items
    document.querySelectorAll('[data-view]').forEach(btn => {
        const btnView = btn.getAttribute('data-view');
        if (btnView === viewName) {
            btn.classList.add('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/30');
            btn.classList.remove('text-slate-300', 'hover:bg-slate-800');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-lg', 'shadow-indigo-500/30');
            btn.classList.add('text-slate-300', 'hover:bg-slate-800');
        }
    });

    // Update breadcrumb
    updateBreadcrumb(viewName);

    // Show/hide views - using camelCase IDs
    document.querySelectorAll('.view-section').forEach(view => {
        view.classList.add('hidden');
    });

    // Convert viewName to camelCase for ID (e.g., 'dashboard' -> 'dashboardView')
    const viewId = viewName + 'View';
    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.classList.remove('hidden');
    }

    // Special handling for upload view
    if (viewName === 'upload') {
        // Reset initialization flag to allow re-initialization
        const uploadZone = document.getElementById('uploadZone');
        if (uploadZone) {
            uploadZone.dataset.initialized = 'false';
            fileUploadInitialized = false;
        }
        
        // Update method indicator
        updateMethodIndicator();
        
        // Update run analysis button
        updateRunAnalysisButton();
        
        // Check if method is selected
        if (!appState.selectedMethod) {
            showNotification('Please select an analysis method first', 'error');
            setTimeout(() => {
                navigateToView('dashboard');
            }, 1500);
            return;
        }
        
        // Re-initialize file upload to ensure event listeners are attached
        setTimeout(() => {
            console.log('Navigating to upload view, re-initializing...');
            initializeFileUpload();
            
            // If we have a file, make sure the UI reflects it
            if (appState.uploadedFile || (typeof apiClient !== 'undefined' && apiClient.getFile())) {
                const file = appState.uploadedFile || apiClient.getFile();
                handleFileSelection(file);
            } else {
                resetUploadView();
            }
        }, 100);
    }
}

function updateBreadcrumb(viewName) {
    const breadcrumbCurrent = document.getElementById('breadcrumbCurrent');
    if (!breadcrumbCurrent) return;

    const breadcrumbMap = {
        'dashboard': 'Dashboard',
        'upload': 'Policy Upload',
        'analysis': 'Analysis Methods',
        'results': 'Results'
    };

    const breadcrumbText = breadcrumbMap[viewName] || 'Dashboard';
    breadcrumbCurrent.textContent = breadcrumbText;
}

// File Upload
let fileUploadInitialized = false;

function initializeFileUpload() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadButton');

    if (!uploadZone || !fileInput) {
        console.warn('Upload elements not found. Upload view might be hidden.');
        // Try again after a short delay in case the view is hidden
        setTimeout(() => {
            const retryUploadZone = document.getElementById('uploadZone');
            const retryFileInput = document.getElementById('fileInput');
            if (retryUploadZone && retryFileInput && !fileUploadInitialized) {
                console.log('Retrying file upload initialization...');
                initializeFileUpload();
            }
        }, 500);
        return;
    }
    
    // Prevent duplicate initialization
    if (fileUploadInitialized && uploadZone.dataset.initialized === 'true') {
        console.log('File upload already initialized');
        return;
    }
    
    console.log('Initializing file upload...');
    
    // Mark as initialized
    uploadZone.dataset.initialized = 'true';
    fileUploadInitialized = true;
    
    // Ensure file input is hidden but accessible
    fileInput.style.display = 'none';
    fileInput.style.visibility = 'hidden';
    fileInput.style.position = 'absolute';
    fileInput.style.width = '0';
    fileInput.style.height = '0';
    fileInput.style.opacity = '0';
    
    // Browse Files button uses inline onclick handler (window.browseFiles)
    // No need to add another event listener here to avoid double-triggering

    // Drag and drop - attach to both uploadZone and fileInput
    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.add('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.remove('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.remove('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    };

    uploadZone.addEventListener('dragover', handleDragOver);
    uploadZone.addEventListener('dragleave', handleDragLeave);
    uploadZone.addEventListener('drop', handleDrop);
    
    // Also attach to fileInput for drag events that might hit it
    fileInput.addEventListener('dragover', handleDragOver);
    fileInput.addEventListener('dragleave', handleDragLeave);
    fileInput.addEventListener('drop', handleDrop);
    
    // Add direct click handler to upload zone as fallback
    uploadZone.addEventListener('click', (e) => {
        // Don't trigger if clicking the browse button, file input, or any button
        const currentFileInput = document.getElementById('fileInput');
        if (e.target.tagName === 'BUTTON' || e.target.closest('button') || e.target === currentFileInput || e.target.id === 'browseFilesBtn') {
            return;
        }
        console.log('Upload zone clicked, triggering file input');
        e.preventDefault();
        e.stopPropagation();
        // Small delay to ensure the click event is processed
        // Get file input dynamically each time to handle element replacement
        setTimeout(() => {
            const fileInputToClick = document.getElementById('fileInput');
            if (fileInputToClick) {
                fileInputToClick.click();
            }
        }, 10);
    });

    // File input change handler - use capture phase to ensure it fires
    fileInput.addEventListener('change', function(e) {
        console.log('File input change event fired', e.target.files);
        const files = e.target.files;
        if (files && files.length > 0) {
            console.log('File selected:', files[0].name, files[0].size);
            handleFileSelection(files[0]);
        } else {
            console.warn('No file selected');
        }
    }, false);
    
    // Also add a direct handler as backup
    fileInput.onchange = function(e) {
        console.log('File input onchange fired', e.target.files);
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFileSelection(files[0]);
        }
    };
    
    // Add click handler to file input for debugging
    fileInput.addEventListener('click', (e) => {
        console.log('File input clicked');
    });
    
    // Test if file input is accessible
    console.log('File input setup:', {
        exists: !!fileInput,
        disabled: fileInput.disabled,
        style: {
            display: fileInput.style.display,
            opacity: fileInput.style.opacity,
            pointerEvents: window.getComputedStyle(fileInput).pointerEvents,
            zIndex: window.getComputedStyle(fileInput).zIndex
        }
    });

    // Upload button
    if (uploadBtn) {
        uploadBtn.addEventListener('click', uploadFile);
    }
}

// Track if file selection is in progress to prevent duplicate calls
let fileSelectionInProgress = false;

function getFileSignature(file) {
    if (!file) return null;
    return `${file.name}-${file.size}-${file.lastModified || ''}`;
}

function handleFileSelection(file) {
    // Prevent duplicate calls
    if (fileSelectionInProgress) {
        console.log('File selection already in progress, skipping duplicate call');
        return;
    }
    
    // Check if same file is already selected
    if (appState.uploadedFile && appState.uploadedFile.name === file.name && appState.uploadedFile.size === file.size) {
        console.log('Same file already selected, skipping');
        return;
    }
    
    fileSelectionInProgress = true;
    console.log('File selected:', file.name, file.size);
    
    // Only accept PDF files
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        fileSelectionInProgress = false;
        showNotification('Please upload a PDF file', 'error');
        return;
    }
    
    // Check file size (16MB max)
    const maxSize = 16 * 1024 * 1024; // 16MB
    if (file.size > maxSize) {
        fileSelectionInProgress = false;
        showNotification('File size must be less than 16MB', 'error');
        return;
    }

    appState.uploadedFile = file;

    // Set file in API client
    if (typeof apiClient !== 'undefined') {
        apiClient.setFile(file);
    }

    // Update UI
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    console.log('Elements found:', { uploadZone: !!uploadZone, filePreview: !!filePreview, fileName: !!fileName, fileSize: !!fileSize });

    // Check if upload view is visible
    const uploadView = document.getElementById('uploadView');
    if (uploadView && uploadView.classList.contains('hidden')) {
        console.warn('Upload view is hidden! Showing it now...');
        uploadView.classList.remove('hidden');
    }

    if (uploadZone && filePreview) {
        console.log('Hiding upload zone and showing file preview');
        
        // Hide upload zone
        uploadZone.style.display = 'none';
        uploadZone.classList.add('hidden');
        
        if (fileInput) {
            fileInput.style.display = 'none';
        }

        // Show file preview - ensure it's visible
        filePreview.classList.remove('hidden');
        filePreview.style.display = 'block';
        filePreview.style.visibility = 'visible';
        filePreview.style.opacity = '1';
        filePreview.style.marginTop = '1.5rem';
        filePreview.style.position = 'relative';
        
        // Ensure parent container is visible
        const previewParent = filePreview.parentElement;
        if (previewParent) {
            previewParent.style.display = 'block';
            console.log('Parent container display:', window.getComputedStyle(previewParent).display);
        }
        
        // Force a reflow to ensure the display change takes effect
        filePreview.offsetHeight;
        
        console.log('File preview display:', window.getComputedStyle(filePreview).display);
        console.log('File preview visibility:', window.getComputedStyle(filePreview).visibility);
        console.log('File preview computed styles:', {
            display: window.getComputedStyle(filePreview).display,
            visibility: window.getComputedStyle(filePreview).visibility,
            opacity: window.getComputedStyle(filePreview).opacity,
            height: window.getComputedStyle(filePreview).height
        });

        // Update file info
        if (fileName) {
            fileName.textContent = file.name;
            console.log('File name set:', file.name);
        }
        if (fileSize) {
            fileSize.textContent = formatFileSize(file.size);
            console.log('File size set:', formatFileSize(file.size));
        }
        
        console.log('File preview should be visible now');
        console.log('File preview computed style:', window.getComputedStyle(filePreview).display);
    } else {
        console.error('Missing elements:', { uploadZone: !!uploadZone, filePreview: !!filePreview });
    }

    // Track new file signature and reset upload status
    appState.fileSignature = getFileSignature(file);
    appState.serverUploadSignature = null;
    
    // Update run analysis button visibility/text
    updateRunAnalysisButton();
    
    console.log('File state:', { 
        uploadedFile: appState.uploadedFile ? appState.uploadedFile.name : null,
        apiClientFile: typeof apiClient !== 'undefined' && apiClient.getFile() ? apiClient.getFile().name : null
    });
    
    // Reset flag after a short delay to allow UI updates
    setTimeout(() => {
        fileSelectionInProgress = false;
    }, 100);
    
    showNotification('File selected successfully!', 'success');
}

function removeFile() {
    appState.uploadedFile = null;
    appState.fileSignature = null;
    appState.serverUploadSignature = null;

    // Clear API client
    if (typeof apiClient !== 'undefined') {
        apiClient.setFile(null);
    }

    // Reset file selection flag
    fileSelectionInProgress = false;

    resetUploadView();
}

function resetUploadView() {
    const uploadZone = document.getElementById('uploadZone');
    const filePreview = document.getElementById('filePreview');
    const fileInput = document.getElementById('fileInput');
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');

    if (uploadZone && filePreview) {
        // Show upload zone
        uploadZone.classList.remove('hidden');
        uploadZone.style.display = 'block';
        
        // Hide file preview
        filePreview.classList.add('hidden');
        filePreview.style.display = 'none';
    }

    if (fileInput) {
        // Properly reset the file input to allow selecting the same file again
        // Create a new input element to replace the old one (this ensures browser treats it as new)
        const newInput = document.createElement('input');
        newInput.type = 'file';
        newInput.id = 'fileInput';
        newInput.accept = '.pdf';
        newInput.style.display = 'none';
        newInput.style.visibility = 'hidden';
        newInput.style.position = 'absolute';
        newInput.style.width = '0';
        newInput.style.height = '0';
        newInput.style.opacity = '0';
        
        // Replace the old input with the new one
        fileInput.parentNode.replaceChild(newInput, fileInput);
        
        // Re-attach the change event listener
        newInput.addEventListener('change', function(e) {
            console.log('File input change event fired', e.target.files);
            const files = e.target.files;
            if (files && files.length > 0) {
                console.log('File selected:', files[0].name, files[0].size);
                handleFileSelection(files[0]);
            } else {
                console.warn('No file selected');
            }
        }, false);
        
        // Also add the onchange handler as backup
        newInput.onchange = function(e) {
            console.log('File input onchange fired', e.target.files);
            const files = e.target.files;
            if (files && files.length > 0) {
                handleFileSelection(files[0]);
            }
        };
        
        // Re-attach drag and drop handlers to the new input
        const handleDragOver = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (uploadZone) {
                uploadZone.classList.add('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');
            }
        };

        const handleDragLeave = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (uploadZone) {
                uploadZone.classList.remove('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');
            }
        };

        const handleDrop = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (uploadZone) {
                uploadZone.classList.remove('border-indigo-500', 'bg-indigo-50', 'dark:bg-indigo-950');
            }

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelection(files[0]);
            }
        };

        newInput.addEventListener('dragover', handleDragOver);
        newInput.addEventListener('dragleave', handleDragLeave);
        newInput.addEventListener('drop', handleDrop);
    }

    // Hide run analysis button
    if (runAnalysisBtn) {
        runAnalysisBtn.classList.add('hidden');
        runAnalysisBtn.disabled = true;
    }
}

async function autoUploadAndAnalyze() {
    if (!appState.uploadedFile || !appState.selectedMethod) {
        showNotification('Please select a method and file first', 'error');
        return;
    }

    const filePreview = document.getElementById('filePreview');

    try {
        // Skip upload step for methods that handle file upload themselves
        // (e.g., /advisor, /score_hybrid_llm, /analyze_comprehensive, /missing_llm)
        const methodsThatHandleUpload = ['score-llm', 'score', 'gap-llm'];
        const shouldSkipUpload = methodsThatHandleUpload.includes(appState.selectedMethod);

        if (!shouldSkipUpload) {
        if (filePreview) {
            const spans = filePreview.querySelectorAll('span');
            let statusBadge = null;
            spans.forEach(span => {
                if (span.textContent.trim() === 'Ready' || span.textContent.includes('Ready')) {
                    statusBadge = span;
                }
            });
            if (statusBadge) {
                statusBadge.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2 inline-block" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Uploading...';
                statusBadge.className = 'flex items-center gap-1 text-indigo-600 dark:text-indigo-400';
            }
        }

        await uploadDocumentIfNeeded({ showNotifications: false, force: true });
        showNotification('Document uploaded! Running analysis...', 'success');
        } else {
            showNotification('Running analysis...', 'info');
        }

        if (filePreview) {
            const spans = filePreview.querySelectorAll('span');
            let statusBadge = null;
            spans.forEach(span => {
                if (span.textContent.includes('Uploading') || span.textContent.includes('Ready') || span.textContent.includes('Analyzing')) {
                    statusBadge = span;
                }
            });
            if (statusBadge) {
                statusBadge.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2 inline-block" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Analyzing...';
                statusBadge.className = 'flex items-center gap-1 text-indigo-600 dark:text-indigo-400';
            }
        }

        await runAnalysis(appState.selectedMethod);

    } catch (error) {
        showNotification(`Upload failed: ${error.message}`, 'error');
        if (filePreview) {
            const statusBadge = filePreview.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.innerHTML = '<svg class="w-4 h-4 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>Ready';
                statusBadge.className = 'status-badge flex items-center gap-2 px-3 py-1.5 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 rounded-full text-xs font-semibold';
            }
        }
    }
}

async function uploadFile() {
    if (!appState.uploadedFile) {
        showNotification('Please select a file first', 'error');
        return;
    }

    const uploadBtn = document.getElementById('uploadButton');
    const originalText = uploadBtn?.textContent || '';

    try {
        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Processing...';
        }

        const formData = new FormData();
        formData.append('file', appState.uploadedFile);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Upload failed');
        }

        const data = await response.json();

        showNotification('Document uploaded successfully!', 'success');

        // Update dashboard
        updateDashboardKPIs();

        // Navigate to analysis
        setTimeout(() => {
            navigateToView('analysis');
        }, 1500);

    } catch (error) {
        showNotification(`Upload failed: ${error.message}`, 'error');
    } finally {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = originalText;
        }
    }
}

// Analysis Methods
async function runAnalysis(method) {
    if (!appState.uploadedFile || (typeof apiClient !== 'undefined' && !apiClient.getFile())) {
        showNotification('Please upload a document first', 'error');
        navigateToView('upload');
        return;
    }

    // Don't navigate away - stay on upload view to show progress
    // The status badge will show "Analyzing..." state
    
    // Try to find method card and button (optional, for UI feedback)
    const methodCard = document.querySelector(`[data-method="${method}"]`);
    const runBtn = methodCard?.querySelector('[data-run-btn]');
    const originalText = runBtn?.innerHTML || '';

    try {
        // Show loading notification
        showNotification('Running analysis...', 'info');
        
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Running...';
        }

        let data;
        let resultTitle = '';

        switch (method) {
            case 'ocr':
                data = await apiClient.testOCR();
                resultTitle = 'OCR Extraction Results';
                break;
            case 'hybrid':
                data = await apiClient.testHybrid();
                resultTitle = 'Hybrid Search Results';
                break;
            case 'rag':
                data = await apiClient.testRAG();
                resultTitle = 'RAG Analysis Results';
                break;
            case 'score':
                data = await apiClient.getScoreHybridLLM();
                resultTitle = 'Gap and Match Analysis (Hybrid + LLM)';
                break;
            case 'score-llm':
                try {
                data = await apiClient.getAdvisorAnalysis();
                    // Log JSON structure for debugging
                    console.log('Advisor Analysis JSON Response:', JSON.stringify(data, null, 2));
                    
                    // Ensure data is valid JSON object
                    if (!data || typeof data !== 'object') {
                        throw new Error('Invalid response format from advisor endpoint');
                    }
                    
                    // Validate required fields
                    if (!data.summary && !data.articles) {
                        console.warn('Advisor response missing expected fields:', data);
                    }
                    
                    // Ensure articles is an array
                    if (data.articles && !Array.isArray(data.articles)) {
                        console.warn('Articles field is not an array, converting...');
                        data.articles = [];
                    }
                    
                resultTitle = 'Compliance Advisor Recommendations';
                } catch (error) {
                    console.error('Error fetching advisor analysis:', error);
                    throw error;
                }
                break;
            case 'gap':
                data = await apiClient.getMissing();
                resultTitle = 'Gap Analysis Results';
                break;
            case 'gap-llm':
                data = await apiClient.getMissingLLM();
                resultTitle = 'LLM Gap Analysis';
                break;
        }

        appState.results = { title: resultTitle, data, method };

        showNotification('Analysis completed successfully!', 'success');
        renderResults();
        navigateToView('results');

    } catch (error) {
        showNotification(`Analysis failed: ${error.message}`, 'error');
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = originalText;
        }
    }
}

// Results Rendering
function renderResults() {
    const resultsContainer = document.getElementById('resultsContainer');
    const resultsTitle = document.getElementById('resultsTitle');

    if (!resultsContainer || !appState.results) return;

    if (resultsTitle) {
        resultsTitle.textContent = appState.results.title;
    }

    const { data, method } = appState.results;
    let html = '';

    if (method === 'score') {
        html = renderScoreResults(data);
    } else if (method === 'score-llm') {
        html = renderAdvisorResults(data);
    } else if (method === 'gap' || method === 'gap-llm') {
        html = renderGapResults(data);
    } else {
        html = renderGeneralResults(data);
    }

    resultsContainer.innerHTML = html;
}

function renderScoreResults(data) {
    console.log('Rendering score results with data:', data);
    const summary = data.summary || {};
    const score = data.overall_score ?? summary.overall_score ?? 0;
    const color = score >= 80 ? 'emerald' : score >= 60 ? 'yellow' : 'rose';
    const complianceLevel = summary.compliance_level || data.compliance_level || null;
    const complianceLevelFormatted = complianceLevel 
        ? complianceLevel.replace(/_/g, ' ').split(' ').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        ).join(' ')
        : getScoreLabel(score);

    let html = `
        <div class="bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 mb-6">
            <div class="text-center mb-8">
                <div class="inline-flex items-center justify-center w-40 h-40 rounded-full bg-${color}-100 dark:bg-${color}-950 border-8 border-${color}-200 dark:border-${color}-900 mb-4">
                    <span class="text-xl font-bold text-${color}-600 dark:text-${color}-400 text-center leading-tight px-3">${complianceLevelFormatted}</span>
                </div>
                <h3 class="text-2xl font-bold text-slate-900 dark:text-white mb-2">Overall Compliance Score</h3>
            </div>
        </div>
    `;

    // Show summary statistics if available
    if (Object.keys(summary).length > 0) {
        // Calculate missing articles count - check multiple sources to ensure accuracy
        let missingCount = summary.articles_missing || 0;
        
        // First, try data.missing_articles
        if (data.missing_articles) {
            missingCount = data.missing_articles.count || (data.missing_articles.article_numbers ? data.missing_articles.article_numbers.length : 0);
        }
        
        // Also check missing_clauses - this is often where the actual missing articles are displayed
        // Count unique article numbers from missing clauses (same logic as line 894-903 below)
        if (data.missing_clauses && (data.missing_clauses.clauses && data.missing_clauses.clauses.length > 0)) {
            const articlesMap = new Map();
            data.missing_clauses.clauses.forEach(clause => {
                const articleNum = clause.article_number;
                if (articleNum && !articlesMap.has(articleNum)) {
                    articlesMap.set(articleNum, true);
                }
            });
            const uniqueArticleCount = articlesMap.size;
            // Use this count if it's greater than what we have, or if we have 0
            if (uniqueArticleCount > 0 && (missingCount === 0 || uniqueArticleCount > missingCount)) {
                missingCount = uniqueArticleCount;
            }
        }
        
        // Debug logging
        console.log('Summary statistics calculation:', {
            'summary.articles_missing': summary.articles_missing,
            'data.missing_articles': data.missing_articles,
            'data.missing_articles.count': data.missing_articles?.count,
            'data.missing_articles.article_numbers.length': data.missing_articles?.article_numbers?.length,
            'data.missing_clauses.clauses.length': data.missing_clauses?.clauses?.length,
            'unique articles from clauses': data.missing_clauses?.clauses ? new Set(data.missing_clauses.clauses.map(c => c.article_number)).size : 0,
            'final missingCount': missingCount
        });
        
        html += `
            <div class="bg-slate-50 dark:bg-slate-800 rounded-xl p-6 mb-6 border border-slate-200 dark:border-slate-700">
                <h3 class="text-lg font-semibold text-slate-900 dark:text-white mb-4">Summary Statistics</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                        <div class="text-2xl font-bold text-slate-900 dark:text-white">${summary.total_articles ?? summary.total_articles_analyzed ?? 0}</div>
                        <div class="text-sm text-slate-600 dark:text-slate-400">Total Articles</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">${summary.covered ?? summary.fully_covered ?? 0}</div>
                        <div class="text-sm text-slate-600 dark:text-slate-400">Fully Covered</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-amber-600 dark:text-amber-400">${summary.partially_covered ?? 0}</div>
                        <div class="text-sm text-slate-600 dark:text-slate-400">Partially Covered</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-rose-600 dark:text-rose-400">${missingCount}</div>
                        <div class="text-sm text-slate-600 dark:text-slate-400">Missing Articles</div>
                    </div>
                </div>
            </div>
        `;
    }

    // Show missing articles if available
    console.log('Checking missing articles:', data.missing_articles);
    if (data.missing_articles && (data.missing_articles.count > 0 || (data.missing_articles.article_numbers && data.missing_articles.article_numbers.length > 0))) {
        const missingCount = data.missing_articles.count || (data.missing_articles.article_numbers ? data.missing_articles.article_numbers.length : 0);
        const articleNumbers = data.missing_articles.article_numbers || [];
        html += `
            <div class="bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-rose-600 dark:text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-rose-900 dark:text-rose-100">Missing Articles: ${missingCount}</h3>
                </div>
                <div class="flex flex-wrap gap-2">
        `;
        
        if (articleNumbers.length > 0) {
            articleNumbers.forEach(articleNum => {
            html += `
                <span class="px-3 py-1 bg-white dark:bg-slate-900 rounded-lg border border-rose-200 dark:border-rose-800 text-sm font-medium text-rose-700 dark:text-rose-300">
                    Article ${articleNum}
                </span>
            `;
            });
        } else {
            html += '<p class="text-sm text-slate-600 dark:text-slate-400">No missing articles found.</p>';
        }
        
        html += '</div></div>';
    } else if (summary.articles_missing > 0) {
        // Fallback: show missing count from summary if missing_articles structure is different
        html += `
            <div class="bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-rose-600 dark:text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-rose-900 dark:text-rose-100">Missing Articles: ${summary.articles_missing}</h3>
                </div>
                <p class="text-sm text-slate-600 dark:text-slate-400">${summary.articles_missing} article(s) were not found in your policy document.</p>
            </div>
        `;
    }

    // Show missing articles if available
    console.log('Checking missing clauses:', data.missing_clauses);
    if (data.missing_clauses && (data.missing_clauses.count > 0 || (data.missing_clauses.clauses && data.missing_clauses.clauses.length > 0))) {
        const clauses = data.missing_clauses.clauses || [];
        
        // Group by article number to avoid duplicates and collect explanations
        const articlesMap = new Map();
        clauses.forEach(clause => {
            const articleNum = clause.article_number;
            if (articleNum && !articlesMap.has(articleNum)) {
                articlesMap.set(articleNum, {
                    article_number: articleNum,
                    explanation: clause.llm_explanation || clause.missing_reason || clause.text || ''
                });
            }
        });
        
        const uniqueArticleCount = articlesMap.size; // Use unique article count, not clause count
        
        html += `
            <div class="bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-rose-600 dark:text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-rose-900 dark:text-rose-100">Missing Articles: ${uniqueArticleCount}</h3>
                </div>
                <div class="space-y-3">
        `;

        if (clauses.length > 0) {
            // Sort by article number
            const sortedArticles = Array.from(articlesMap.values()).sort((a, b) => 
                (a.article_number || 0) - (b.article_number || 0)
            );
            
            sortedArticles.forEach(article => {
            html += `
                <div class="bg-white dark:bg-slate-900 rounded-lg p-4 border border-rose-200 dark:border-rose-800">
                        <h4 class="font-semibold text-slate-900 dark:text-white mb-2">Article ${article.article_number}</h4>
                        ${article.explanation ? `<p class="text-sm text-slate-600 dark:text-slate-400">${article.explanation}</p>` : ''}
                </div>
            `;
            });
        } else {
            html += '<p class="text-sm text-slate-600 dark:text-slate-400">No missing articles found.</p>';
        }

        html += '</div></div>';
    }

    // Show partially covered clauses if available
    console.log('Checking partially covered clauses:', data.partially_covered_clauses);
    if (data.partially_covered_clauses && (data.partially_covered_clauses.count > 0 || (data.partially_covered_clauses.clauses && data.partially_covered_clauses.clauses.length > 0))) {
        const partialClauses = data.partially_covered_clauses.clauses || [];
        const partialCount = data.partially_covered_clauses.count || partialClauses.length;
        html += `
            <div class="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-amber-900 dark:text-amber-100">Partially Covered Articles: ${partialCount}</h3>
                </div>
                <div class="space-y-3">
        `;

        if (partialClauses.length > 0) {
            // Group by article number to avoid duplicates
            const articlesMap = new Map();
            partialClauses.forEach(clause => {
                const articleNum = clause.article_number;
                if (!articlesMap.has(articleNum)) {
                    articlesMap.set(articleNum, {
                        article_number: articleNum,
                        explanation: clause.llm_explanation || clause.partial_reason || clause.text || ''
                    });
                }
            });
            
            // Sort by article number
            const sortedArticles = Array.from(articlesMap.values()).sort((a, b) => 
                (a.article_number || 0) - (b.article_number || 0)
            );
            
            sortedArticles.forEach(article => {
            html += `
                <div class="bg-white dark:bg-slate-900 rounded-lg p-4 border border-amber-200 dark:border-amber-800">
                        <h4 class="font-semibold text-slate-900 dark:text-white mb-2">Article ${article.article_number}</h4>
                        ${article.explanation ? `<p class="text-sm text-slate-600 dark:text-slate-400">${article.explanation}</p>` : ''}
                </div>
            `;
            });
        } else {
            html += '<p class="text-sm text-slate-600 dark:text-slate-400">No partially covered articles found.</p>';
        }

        html += '</div></div>';
    }

    // Show covered articles if available
    if (summary.covered_list && summary.covered_list.length > 0) {
        const coveredCount = summary.covered_list.length;
        // Sort covered articles by number
        const sortedCovered = [...summary.covered_list].sort((a, b) => (a || 0) - (b || 0));
        html += `
            <div class="bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-emerald-900 dark:text-emerald-100">Covered Articles: ${coveredCount}</h3>
                </div>
                <div class="flex flex-wrap gap-2">
        `;

        sortedCovered.forEach(articleNum => {
            html += `
                <span class="px-3 py-1 bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300 rounded-full text-sm font-medium">
                    Article ${articleNum}
                </span>
            `;
        });

        html += '</div></div>';
    }

    // Show requirements if available (for backward compatibility)
    if (data.requirements && data.requirements.length > 0) {
        html += '<div class="space-y-4">';
        data.requirements.forEach(req => {
            const reqScore = req.score || 0;
            const reqColor = reqScore >= 80 ? 'emerald' : reqScore >= 60 ? 'yellow' : 'rose';

            html += `
                <div class="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800">
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex-1">
                            <h4 class="font-semibold text-slate-900 dark:text-white mb-2">${req.requirement || 'Unknown'}</h4>
                            <p class="text-sm text-slate-600 dark:text-slate-400">${req.explanation || ''}</p>
                        </div>
                        <span class="ml-4 px-3 py-1 rounded-full text-sm font-semibold bg-${reqColor}-100 dark:bg-${reqColor}-950 text-${reqColor}-700 dark:text-${reqColor}-300">
                            ${reqScore}%
                        </span>
                    </div>
                    ${req.evidence ? `
                        <div class="mt-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                            <p class="text-sm text-slate-700 dark:text-slate-300">${req.evidence}</p>
                        </div>
                    ` : ''}
                </div>
            `;
        });
        html += '</div>';
    }

    return html;
}

function renderAdvisorResults(data) {
    const summary = data.summary || {};
    const score = summary.overall_score ?? data.overall_score ?? 0;
    const color = score >= 80 ? 'emerald' : score >= 60 ? 'amber' : 'rose';
    const complianceLevel = summary.compliance_level || data.compliance_level || 'Not available';
    const complianceLevelFormatted = complianceLevel.replace(/_/g, ' ').split(' ').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
    const coveredCount = summary.covered_articles_count ?? summary.covered ?? 0;
    const needsCount = summary.needs_improvement_count ?? 0;
    const totalAnalyzed = summary.total_articles_analyzed ?? summary.total_articles ?? (Array.isArray(data.articles) ? data.articles.length : 0);

    let html = `
        <div class="bg-white dark:bg-slate-900 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 mb-6">
            <div class="text-center mb-8">
                <div class="inline-flex items-center justify-center w-40 h-40 rounded-full bg-${color}-100 dark:bg-${color}-950 border-8 border-${color}-200 dark:border-${color}-900 mb-4">
                    <span class="text-xl font-bold text-${color}-600 dark:text-${color}-400 text-center leading-tight px-3">${complianceLevelFormatted}</span>
                </div>
                <h3 class="text-2xl font-bold text-slate-900 dark:text-white mb-2">Overall Compliance Score</h3>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <div class="text-2xl font-bold text-slate-900 dark:text-white">${totalAnalyzed}</div>
                    <div class="text-sm text-slate-600 dark:text-slate-400">Articles Analyzed</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">${coveredCount}</div>
                    <div class="text-sm text-slate-600 dark:text-slate-400">Covered</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-amber-600 dark:text-amber-400">${needsCount}</div>
                    <div class="text-sm text-slate-600 dark:text-slate-400">Needs Work</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-slate-900 dark:text-white">${summary.coverage_threshold ?? data.coverage_threshold ?? 80}%</div>
                    <div class="text-sm text-slate-600 dark:text-slate-400">Coverage Threshold</div>
                </div>
            </div>
        </div>
    `;

    if (Array.isArray(data.articles) && data.articles.length > 0) {
        // Sort articles by compliance level: Not Compliant first, then Partially Compliant, then Compliant
        const sortedArticles = [...data.articles].sort((a, b) => {
            const getComplianceOrder = (percentage) => {
                if (percentage >= 75) return 3; // Compliant - last
                if (percentage >= 40) return 2; // Partially Compliant - middle
                return 1; // Not Compliant - first
            };
            
            const orderA = getComplianceOrder(a.coverage_percentage || 0);
            const orderB = getComplianceOrder(b.coverage_percentage || 0);
            
            // If same compliance level, sort by article number
            if (orderA === orderB) {
                return (a.article_number || 0) - (b.article_number || 0);
            }
            
            return orderA - orderB;
        });
        
        html += '<div class="space-y-4">';

        sortedArticles.forEach(article => {
            const statusIsCovered = article.status === 'covered';
            const coveragePercentage = article.coverage_percentage || 0;
            
            // Determine compliance level based on coverage percentage
            let complianceLevel;
            let complianceColor;
            if (coveragePercentage >= 75) {
                complianceLevel = 'Compliant';
                complianceColor = 'emerald';
            } else if (coveragePercentage >= 40) {
                complianceLevel = 'Partially Compliant';
                complianceColor = 'amber';
            } else {
                complianceLevel = 'Not Compliant';
                complianceColor = 'rose';
            }
            
            // Determine badge text and color based on compliance level
            let badgeText;
            let badgeColor;
            if (statusIsCovered) {
                badgeText = 'Covered';
                badgeColor = 'emerald';
            } else if (complianceLevel === 'Not Compliant') {
                badgeText = 'Out of Compliance Scope';
                badgeColor = 'rose';
            } else {
                badgeText = 'Needs Improvement';
                badgeColor = 'amber';
            }
            
            // Determine status box color based on compliance level
            // Not Compliant = red (rose), Partially Compliant = yellow (amber)
            let statusBoxClasses = '';
            let statusTextClasses = '';
            let statusTextClassesSecondary = '';
            if (complianceLevel === 'Not Compliant') {
                statusBoxClasses = 'bg-rose-50 dark:bg-rose-950 border-rose-200 dark:border-rose-800';
                statusTextClasses = 'text-rose-700 dark:text-rose-300';
                statusTextClassesSecondary = 'text-rose-600 dark:text-rose-400';
            } else if (complianceLevel === 'Partially Compliant') {
                statusBoxClasses = 'bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800';
                statusTextClasses = 'text-amber-700 dark:text-amber-300';
                statusTextClassesSecondary = 'text-amber-600 dark:text-amber-400';
            } else {
                statusBoxClasses = 'bg-emerald-50 dark:bg-emerald-950 border-emerald-200 dark:border-emerald-800';
                statusTextClasses = 'text-emerald-700 dark:text-emerald-300';
                statusTextClassesSecondary = 'text-emerald-600 dark:text-emerald-400';
            }
            
            html += `
                <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                    <div class="flex flex-wrap items-start justify-between gap-4 mb-4">
                        <div>
                            <h4 class="text-xl font-semibold text-slate-900 dark:text-white">Article ${article.article_number || '—'}</h4>
                        </div>
                        <span class="px-3 py-1 rounded-full bg-${badgeColor}-100 dark:bg-${badgeColor}-900 text-${badgeColor}-700 dark:text-${badgeColor}-300 text-sm font-semibold">
                            ${badgeText}
                        </span>
                    </div>
                    <div class="flex flex-wrap items-center gap-4 mb-4">
                        <div class="flex items-center gap-2">
                            <span class="text-2xl font-bold text-${complianceColor}-600 dark:text-${complianceColor}-400">${complianceLevel}</span>
                        </div>
                    </div>
                    ${article.recommendation && Array.isArray(article.recommendation) && article.recommendation.length > 0 ? `
                        <div class="p-4 bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 rounded-lg mb-4">
                            <p class="text-sm font-semibold text-indigo-900 dark:text-indigo-100 mb-3">Recommendations</p>
                            <div class="space-y-4">
                                ${article.recommendation.map(rec => `
                                    <div class="bg-white dark:bg-slate-800 rounded-lg p-4 border border-indigo-200 dark:border-indigo-800">
                                        <div class="flex items-start gap-2 mb-3">
                                            <span class="px-2 py-1 bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-xs font-semibold rounded">Recommendation ${rec.recommendation_number || ''}</span>
                                            <span class="px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium rounded">${rec.pdpl_reference || ''}</span>
                                        </div>
                                        ${rec.current_policy_text && rec.current_policy_text !== 'Not found' ? `
                                        <div class="mb-3 p-3 ${statusBoxClasses} border rounded">
                                            <p class="text-xs font-semibold ${statusTextClasses} mb-1">Current Policy Text (Needs Change):</p>
                                            <p class="text-sm ${statusTextClassesSecondary} italic">"${rec.current_policy_text}"</p>
                                        </div>
                                        ` : rec.current_policy_text === 'Not found' ? `
                                        <div class="mb-3 p-3 ${statusBoxClasses} border rounded">
                                            <p class="text-xs font-semibold ${statusTextClasses} mb-1">Status:</p>
                                            <p class="text-sm ${statusTextClassesSecondary}">This requirement is missing from the policy and needs to be added.</p>
                        </div>
                    ` : ''}
                                        <div class="mb-3">
                                            <p class="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Action:</p>
                                            <p class="text-sm text-slate-600 dark:text-slate-400">${rec.action || ''}</p>
                        </div>
                                        <div>
                                            <p class="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Suggested Policy Text:</p>
                                            <p class="text-sm text-slate-600 dark:text-slate-400 italic">${rec.sample_policy_wording || ''}</p>
                        </div>
                        </div>
                                `).join('')}
                    </div>
                        </div>
                    ` : article.recommendation && typeof article.recommendation === 'string' ? `
                        <div class="p-4 bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 rounded-lg mb-4">
                            <p class="text-sm font-semibold text-indigo-900 dark:text-indigo-100 mb-1">Recommendation</p>
                            <p class="text-sm text-indigo-700 dark:text-indigo-300">${article.recommendation}</p>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div>';
    } else {
        html += `
            <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                <p class="text-sm text-slate-600 dark:text-slate-400">No article-level recommendations were returned.</p>
            </div>
        `;
    }

    return html;
}

function renderGapResults(data) {
    let html = '';

    if (data.missing_requirements && data.missing_requirements.length > 0) {
        html += `
            <div class="bg-rose-50 dark:bg-rose-950 border border-rose-200 dark:border-rose-800 rounded-xl p-6 mb-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-rose-600 dark:text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-rose-900 dark:text-rose-100">Missing Requirements: ${data.missing_requirements.length}</h3>
                </div>
                <div class="space-y-3">
        `;

        data.missing_requirements.forEach(req => {
            html += `
                <div class="bg-white dark:bg-slate-900 rounded-lg p-4 border border-rose-200 dark:border-rose-800">
                    <h4 class="font-semibold text-slate-900 dark:text-white mb-2">${req.requirement || 'Unknown'}</h4>
                    <p class="text-sm text-slate-600 dark:text-slate-400 mb-3">${req.explanation || ''}</p>
                    ${req.recommendation ? `
                        <div class="p-3 bg-indigo-50 dark:bg-indigo-950 rounded-lg border border-indigo-200 dark:border-indigo-800">
                            <p class="text-sm font-medium text-indigo-900 dark:text-indigo-100 mb-1">Recommendation:</p>
                            <p class="text-sm text-indigo-700 dark:text-indigo-300">${req.recommendation}</p>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += '</div></div>';
    }

    if (data.compliant_requirements && data.compliant_requirements.length > 0) {
        html += `
            <div class="bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-xl p-6">
                <div class="flex items-center gap-3 mb-4">
                    <svg class="w-6 h-6 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3 class="text-xl font-bold text-emerald-900 dark:text-emerald-100">Compliant Requirements: ${data.compliant_requirements.length}</h3>
                </div>
                <div class="space-y-2">
        `;

        data.compliant_requirements.forEach(req => {
            html += `
                <div class="flex items-start gap-3 p-3 bg-white dark:bg-slate-900 rounded-lg border border-emerald-200 dark:border-emerald-800">
                    <svg class="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    <span class="text-sm text-slate-700 dark:text-slate-300">${req}</span>
                </div>
            `;
        });

        html += '</div></div>';
    }

    return html || '<p class="text-slate-600 dark:text-slate-400">No gap analysis data available.</p>';
}

function renderGeneralResults(data) {
    return `
        <div class="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800">
            <pre class="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">${JSON.stringify(data, null, 2)}</pre>
        </div>
    `;
}

// Dashboard KPIs
async function updateDashboardKPIs() {
    // This would typically fetch real data from the backend
    // For now, we'll use placeholder logic
    const uploadedCount = appState.uploadedFile ? 1 : 0;

    const kpiElements = {
        uploaded: document.querySelector('[data-kpi="uploaded"]'),
        score: document.querySelector('[data-kpi="score"]'),
        gaps: document.querySelector('[data-kpi="gaps"]'),
        status: document.querySelector('[data-kpi="status"]')
    };

    if (kpiElements.uploaded) {
        kpiElements.uploaded.textContent = uploadedCount;
    }
}

// Utility Functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getScoreLabel(score) {
    if (score >= 90) return 'Excellent Compliance';
    if (score >= 80) return 'Good Compliance';
    if (score >= 70) return 'Moderate Compliance';
    if (score >= 60) return 'Fair Compliance';
    return 'Needs Improvement';
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('notificationContainer') || createNotificationContainer();

    const colors = {
        success: 'bg-emerald-500',
        error: 'bg-rose-500',
        info: 'bg-indigo-500'
    };

    const notification = document.createElement('div');
    notification.className = `${colors[type]} text-white px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 mb-3 transform transition-all duration-300 translate-x-0`;
    notification.innerHTML = `
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <span>${message}</span>
    `;

    container.appendChild(notification);

    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notificationContainer';
    container.className = 'fixed top-20 right-4 z-50 w-96';
    document.body.appendChild(container);
    return container;
}

function clearFile() {
    removeFile();
}

function toggleAnalysisDropdown() {
    const dropdown = document.getElementById('analysisDropdown');
    const icon = document.getElementById('analysisDropdownIcon');
    
    if (dropdown && icon) {
        const isHidden = dropdown.classList.contains('hidden');
        if (isHidden) {
            dropdown.classList.remove('hidden');
            icon.style.transform = 'rotate(180deg)';
        } else {
            dropdown.classList.add('hidden');
            icon.style.transform = 'rotate(0deg)';
        }
    }
}

function selectMethodAndUpload(method) {
    appState.selectedMethod = method;
    console.log('Method selected:', method);
    
    // Close the dropdown
    const dropdown = document.getElementById('analysisDropdown');
    const icon = document.getElementById('analysisDropdownIcon');
    if (dropdown && icon) {
        dropdown.classList.add('hidden');
        icon.style.transform = 'rotate(0deg)';
    }
    
    // Update method indicator if upload view is visible
    updateMethodIndicator();
    
    // Update run analysis button
    updateRunAnalysisButton();
    
    // Navigate to upload view
    navigateToView('upload');
}

function updateMethodIndicator() {
    const indicator = document.getElementById('selectedMethodIndicator');
    const methodName = document.getElementById('selectedMethodName');
    const methodDesc = document.getElementById('selectedMethodDesc');
    
    if (!indicator || !appState.selectedMethod) return;
    
    if (appState.selectedMethod === 'score') {
        indicator.classList.remove('hidden');
        if (methodName) methodName.textContent = 'Gap and Match Analysis';
        if (methodDesc) methodDesc.textContent = 'Quick analysis powered by semantic matching technology';
        indicator.className = indicator.className.replace(/bg-\w+-\d+|border-\w+-\d+/g, '');
        indicator.classList.add('bg-blue-50', 'dark:bg-blue-950', 'border-blue-200', 'dark:border-blue-800');
    } else if (appState.selectedMethod === 'score-llm') {
        indicator.classList.remove('hidden');
        if (methodName) methodName.textContent = 'Recommendation Analysis';
        if (methodDesc) methodDesc.textContent = 'Comprehensive AI analysis with enhanced accuracy and contextual understanding';
        indicator.className = indicator.className.replace(/bg-\w+-\d+|border-\w+-\d+/g, '');
        indicator.classList.add('bg-indigo-50', 'dark:bg-indigo-950', 'border-indigo-200', 'dark:border-indigo-800');
    }
}

async function uploadDocumentIfNeeded(options = {}) {
    const { showNotifications = true, force = false } = options;
    
    if (!appState.uploadedFile) {
        showNotification('Please upload a file first', 'error');
        throw new Error('No file selected');
    }
    
    const currentSignature = appState.fileSignature || getFileSignature(appState.uploadedFile);
    
    if (!force && appState.serverUploadSignature && appState.serverUploadSignature === currentSignature) {
        return;
    }
    
    if (showNotifications) {
        showNotification('Uploading document...', 'info');
    }
    
    const formData = new FormData();
    formData.append('file', appState.uploadedFile);

    const response = await fetch('/upload', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        throw new Error('Upload failed');
    }

    await response.json();
    
    updateDashboardKPIs();
    appState.serverUploadSignature = currentSignature;
    
    if (showNotifications) {
        showNotification('Document uploaded successfully!', 'success');
    }
}

function updateRunAnalysisButton() {
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    if (!runAnalysisBtn) return;
    
    if (!appState.selectedMethod || !appState.uploadedFile) {
        runAnalysisBtn.classList.add('hidden');
        runAnalysisBtn.disabled = true;
        return;
    }
    
    runAnalysisBtn.disabled = false;
    
    // Show the button
    runAnalysisBtn.classList.remove('hidden');
    
    // Update button text and styling based on method
    if (appState.selectedMethod === 'score') {
        runAnalysisBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            <span>Run Analysis for Gap and Match Analysis</span>
        `;
        runAnalysisBtn.className = 'w-full flex items-center justify-center gap-2 px-6 py-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40';
    } else if (appState.selectedMethod === 'score-llm') {
        runAnalysisBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            <span>Run Analysis for Recommendation Analysis</span>
        `;
        runAnalysisBtn.className = 'w-full flex items-center justify-center gap-2 px-6 py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40';
    }
}

async function runSelectedAnalysis() {
    if (!appState.selectedMethod) {
        showNotification('No analysis method selected', 'error');
        return;
    }
    
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const originalRunHTML = runAnalysisBtn ? runAnalysisBtn.innerHTML : '';
    
    // Show loading state
    if (runAnalysisBtn) {
        runAnalysisBtn.disabled = true;
        runAnalysisBtn.innerHTML = `
            <svg class="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Running...</span>
        `;
        runAnalysisBtn.classList.add('opacity-75', 'cursor-not-allowed');
    }
    
    try {
        // Skip upload step for methods that handle file upload themselves
        // (e.g., /advisor, /score_hybrid_llm, /analyze_comprehensive, /missing_llm)
        const methodsThatHandleUpload = ['score-llm', 'score', 'gap-llm'];
        const shouldSkipUpload = methodsThatHandleUpload.includes(appState.selectedMethod);
        
        if (!shouldSkipUpload) {
        await uploadDocumentIfNeeded();
        }
        await runAnalysis(appState.selectedMethod);
        
        // Restore button state after analysis completes
        if (runAnalysisBtn) {
            runAnalysisBtn.disabled = false;
            runAnalysisBtn.innerHTML = originalRunHTML;
            runAnalysisBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        }
    } catch (error) {
        if (error && error.message) {
            showNotification(error.message, 'error');
        }
        // Restore button state on error
        if (runAnalysisBtn) {
            runAnalysisBtn.disabled = false;
            runAnalysisBtn.innerHTML = originalRunHTML;
            runAnalysisBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        }
    }
}

function closeHelp() {
    const modal = document.getElementById('helpModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function showHelp() {
    const modal = document.getElementById('helpModal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

// Global function to trigger file input (backup for button)
window.browseFiles = function() {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        console.log('browseFiles() called, triggering file input');
        fileInput.click();
    } else {
        console.error('File input not found in browseFiles()');
    }
};

// Export functions to global scope for inline handlers
window.toggleDarkMode = toggleDarkMode;
window.navigateToView = navigateToView;
window.removeFile = removeFile;
window.uploadFile = uploadFile;
window.runAnalysis = runAnalysis;
window.runSelectedAnalysis = runSelectedAnalysis;
window.clearFile = clearFile;
window.selectMethodAndUpload = selectMethodAndUpload;
window.toggleAnalysisDropdown = toggleAnalysisDropdown;
window.closeHelp = closeHelp;
window.showHelp = showHelp;
