class APIClient {
    constructor() {
        this.currentFile = null;
    }

    setFile(file) {
        this.currentFile = file;
    }

    getFile() {
        return this.currentFile;
    }

    async makeRequest(endpoint, file = null) {
        const formData = new FormData();
        const fileToUse = file || this.currentFile;

        if (!fileToUse) {
            throw new Error('No file selected');
        }

        formData.append('file', fileToUse);

        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: `;
            try {
                const errorData = await response.json();
                errorMessage += errorData.detail || errorData.message || JSON.stringify(errorData);
            } catch (e) {
            const errorText = await response.text();
                errorMessage += errorText;
            }
            throw new Error(errorMessage);
        }

        // Ensure response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Response is not JSON format');
        }

        try {
            const jsonData = await response.json();
            return jsonData;
        } catch (e) {
            throw new Error('Failed to parse JSON response: ' + e.message);
        }
    }

    async testOCR() {
        return await this.makeRequest('/test/ocr');
    }

    async testHybrid() {
        return await this.makeRequest('/test/hybrid');
    }

    async testRAG() {
        return await this.makeRequest('/test/rag');
    }

    async getScore() {
        return await this.makeRequest('/score');
    }

    async getScoreHybridLLM() {
        return await this.makeRequest('/score_hybrid_llm');
    }

    async getScoreLLM() {
        return await this.makeRequest('/score_llm');
    }

    async getAdvisorAnalysis() {
        return await this.makeRequest('/advisor');
    }

    async getMissing() {
        return await this.makeRequest('/missing');
    }

    async getMissingLLM() {
        return await this.makeRequest('/missing_llm');
    }

    async getComprehensiveAnalysis() {
        return await this.makeRequest('/analyze_comprehensive');
    }

    async uploadFile() {
        return await this.makeRequest('/upload');
    }
}

const apiClient = new APIClient();
