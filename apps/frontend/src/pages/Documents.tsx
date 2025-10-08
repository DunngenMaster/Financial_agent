import { useState, useEffect } from 'react';
import { processAPI } from '../api/config';
import { DocumentTextIcon, PaperAirplaneIcon, TrashIcon } from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Document {
  doc_id: string;
  filename: string;
  processed_date: string;
  content?: string;
  metadata?: any;
}

interface Message {
  type: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

type TabKey = 'chat' | 'invest';

export default function Documents() {
  const [documents, setDocuments] = useState<Record<string, Document>>({});
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [polling, setPolling] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedPersona, setSelectedPersona] = useState('general');
  const [activeTab, setActiveTab] = useState<TabKey>('chat');

  // Investment analysis state
  const [company, setCompany] = useState('');
  const [investLoading, setInvestLoading] = useState(false);
  const [investResult, setInvestResult] = useState<null | {
    decision: string;
    likelihood_percent: number;
    rationale: string;
    forecast_points: string[];
    company?: string;
  }>(null);

  const personas = {
    general: { name: 'General Investor', icon: '👥', color: 'bg-gray-500' },
    tech: { name: 'Tech Investor', icon: '💻', color: 'bg-blue-500' },
    value: { name: 'Value Investor', icon: '💎', color: 'bg-green-500' },
    growth: { name: 'Growth Investor', icon: '📈', color: 'bg-purple-500' },
    esg: { name: 'ESG Investor', icon: '🌱', color: 'bg-emerald-500' },
    institutional: { name: 'Institutional', icon: '🏦', color: 'bg-indigo-500' },
    retail: { name: 'Retail Investor', icon: '🏠', color: 'bg-orange-500' },
    risk: { name: 'Risk Manager', icon: '🛡️', color: 'bg-red-500' }
  };

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;

    const fetchDocuments = async () => {
      try {
        const response = await processAPI.get('/documents');
        setDocuments(response.data || {});
      } catch {}
    };

    if (polling) {
      fetchDocuments();
      interval = setInterval(fetchDocuments, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [polling]);

  const handleFilesUpload = async (files: FileList) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      for (const file of fileArray) {
        if (!file.type.toLowerCase().includes('pdf')) {
          setError(prev => (prev ? prev + '\n' : '') + `Skip: ${file.name} (not a PDF)`);
          continue;
        }
        const formData = new FormData();
        formData.append('file', file);

        const response = await processAPI.post('/process/pdf', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });

        if (response.data?.status === 'success') {
          setSuccess(prev => (prev ? prev + '\n' : '') + `Uploaded: ${file.name}`);
        } else {
          setError(prev => (prev ? prev + '\n' : '') + `Failed: ${file.name}`);
        }
      }

      const docsResponse = await processAPI.get('/documents');
      setDocuments(docsResponse.data || {});
      setTimeout(() => setSuccess(''), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const clearDocuments = async () => {
    try {
      setPolling(false);
      setDocuments({});
      setSelectedDoc(null);
      setMessages([]);
      setInvestResult(null);
      setError('');
      setSuccess('');

      const response = await processAPI.post('/clear/documents');
      if (response.data?.status === 'success') {
        setSuccess('All documents cleared successfully');
        setTimeout(() => setSuccess(''), 2500);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to clear documents');
    } finally {
      setPolling(true);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (Object.keys(documents).length === 0 || !input.trim() || loading) return;

    const userMessage = input.trim();
    const timestamp = Date.now();

    setMessages(prev => [...prev, { type: 'user', content: userMessage, timestamp }]);
    setInput('');
    setLoading(true);

    try {
      let response;
      if (selectedDoc) {
        response = await processAPI.post('/query', {
          doc_id: selectedDoc.doc_id,
          question: userMessage,
          timestamp,
          persona: selectedPersona
        });
      } else {
        const docIds = Object.keys(documents);
        response = await processAPI.post('/query/multi', {
          doc_ids: docIds,
          question: userMessage,
          timestamp,
          persona: selectedPersona
        });
      }

      if (response.data.status === 'ok' && response.data.answers?.length > 0) {
        setMessages(prev => [
          ...prev,
          { type: 'assistant', content: response.data.answers[0], timestamp: Date.now() }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          { type: 'assistant', content: 'No answer returned.', timestamp: Date.now() }
        ]);
      }
    } catch (e: any) {
      setMessages(prev => [
        ...prev,
        { type: 'assistant', content: `Error: ${e?.response?.data?.detail || e.message}`, timestamp: Date.now() }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const runInvestmentAnalysis = async () => {
    if (Object.keys(documents).length === 0 || investLoading) return;
    setInvestLoading(true);
    setInvestResult(null);
    setError('');

    try {
      const docIds = selectedDoc ? [selectedDoc.doc_id] : Object.keys(documents);
      const resp = await processAPI.post('/invest/analyze', {
        doc_ids: docIds,
        persona: selectedPersona,
        company: company || undefined,
        top_k: 5
      });

      if (resp.data?.status === 'ok') {
        setInvestResult({
          decision: resp.data.decision,
          likelihood_percent: resp.data.likelihood_percent,
          rationale: resp.data.rationale,
          forecast_points: resp.data.forecast_points || [],
          company: resp.data.company
        });
        setActiveTab('invest');
      } else {
        setError('Investment analysis failed.');
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Investment analysis failed');
    } finally {
      setInvestLoading(false);
    }
  };

  // Simple meter component
  const LikelihoodBar = ({ value }: { value: number }) => {
    const pct = Math.max(0, Math.min(100, Math.round(value)));
    return (
      <div>
        <div className="h-3 w-full bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-3 ${pct >= 60 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-500'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-gray-600">{pct}% likelihood</div>
      </div>
    );
  };

  return (
    <div className="h-screen flex bg-gray-100">
      {/* Sidebar */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-xl font-semibold text-gray-800">Financial Agent</h1>

          {/* File Upload */}
          <div className="mt-4">
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".pdf"
              multiple
              onChange={(e) => e.target.files && handleFilesUpload(e.target.files)}
            />
            <label
              htmlFor="file-upload"
              className={`inline-flex items-center justify-center w-full px-4 py-2 text-sm font-medium rounded-md cursor-pointer ${
                uploading ? 'bg-gray-200 text-gray-500' : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {uploading ? 'Uploading…' : 'Upload PDF(s)'}
            </label>
          </div>

          {/* Clear All Button */}
          {Object.keys(documents).length > 0 && (
            <div className="mt-4">
              <button
                onClick={clearDocuments}
                className="inline-flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 transition-colors"
                disabled={uploading}
              >
                <TrashIcon className="w-4 h-4 mr-2" />
                Clear All Documents
              </button>
            </div>
          )}

          {/* Persona Selector */}
          <div className="mt-6 border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-3">Analysis Persona</h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {Object.entries(personas).map(([key, persona]) => (
                <button
                  key={key}
                  onClick={() => setSelectedPersona(key)}
                  className={`w-full flex items-center px-3 py-2 text-sm rounded-md transition-colors ${
                    selectedPersona === key
                      ? persona.color + ' text-white shadow-sm'
                      : 'bg-gray-50 text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-base mr-3">{persona.icon}</span>
                  <span className="font-medium">{persona.name}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">AI will tailor analysis to your investment focus</p>
          </div>
        </div>

        {/* Document List */}
        <div className="flex-1 overflow-y-auto p-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Documents</h3>
          {Object.entries(documents).map(([id, doc]) => (
            <button
              key={id}
              onClick={() => { setSelectedDoc(doc); setMessages([]); }}
              className={`w-full flex items-center p-3 mb-2 rounded-lg text-left transition-colors ${
                selectedDoc?.doc_id === id
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              <DocumentTextIcon className="w-5 h-5 mr-3 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{doc.filename}</p>
                <p className="text-xs text-gray-500">{new Date(doc.processed_date).toLocaleString()}</p>
              </div>
            </button>
          ))}

          {Object.keys(documents).length > 1 && (
            <button
              onClick={() => { setSelectedDoc(null); setMessages([]); }}
              className={`w-full px-4 py-2 text-sm font-medium rounded-md mb-2 ${
                !selectedDoc
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-gray-50 text-gray-700 hover:bg-gray-100'
              }`}
            >
              Query All Documents
            </button>
          )}

          {Object.keys(documents).length === 0 && !uploading && (
            <div className="text-center py-8 text-gray-500">
              <DocumentTextIcon className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p>Upload a PDF to get started</p>
            </div>
          )}
        </div>
      </div>

      {/* Right side */}
      <div className="flex-1 flex flex-col">
        {/* Tabs */}
        <div className="border-b border-gray-200 bg-white px-4">
          <div className="flex space-x-4">
            {(['chat','invest'] as TabKey[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-3 px-2 border-b-2 -mb-px text-sm font-medium ${
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
                }`}
              >
                {tab === 'chat' ? 'Chat' : 'Investment'}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        {activeTab === 'chat' ? (
          <>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {error && <div className="p-4 bg-red-50 text-red-600 rounded-lg whitespace-pre-line">{error}</div>}
              {success && <div className="p-4 bg-green-50 text-green-600 rounded-lg whitespace-pre-line">{success}</div>}

              {messages.map((message, index) => (
                <div key={message.timestamp || index} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-3xl rounded-lg px-4 py-3 ${
                      message.type === 'user' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 shadow-sm'
                    }`}
                  >
                    {message.type === 'assistant' && (
                      <div className="flex items-center mb-2 text-xs text-gray-500">
                        <span className={
                          (personas as any)[selectedPersona].color + ' text-white px-2 py-1 rounded-full mr-2'
                        }>
                          {(personas as any)[selectedPersona].icon} {(personas as any)[selectedPersona].name}
                        </span>
                      </div>
                    )}

                    {message.type === 'assistant' ? (
                      <div className="text-sm prose prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-lg px-4 py-3">
                    <div className="flex items-center space-x-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                      <span className="text-sm text-gray-600">
                        Analyzing as {(personas as any)[selectedPersona].name}…
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {messages.length === 0 && Object.keys(documents).length > 0 && (
                <div className="text-center text-gray-500">
                  <div className="mb-4">
                    <span className="text-lg">
                      {selectedDoc ? `Ask a question about ${selectedDoc.filename}` : `Ask questions about your ${Object.keys(documents).length} uploaded documents`}
                    </span>
                  </div>
                  <div className="text-sm">
                    <span className={
                      (personas as any)[selectedPersona].color + ' text-white px-3 py-1 rounded-full text-xs'
                    }>
                      {(personas as any)[selectedPersona].icon} Analysis Style: {(personas as any)[selectedPersona].name}
                    </span>
                  </div>
                </div>
              )}

              {Object.keys(documents).length === 0 && (
                <div className="text-center text-gray-500">Upload documents to start asking questions</div>
              )}
            </div>

            {Object.keys(documents).length > 0 && (
              <div className="border-t border-gray-200 p-4">
                <form onSubmit={handleSubmit} className="flex space-x-4">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={selectedDoc ? `Ask about ${selectedDoc.filename}…` : `Ask about your documents…`}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || loading}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center"
                  >
                    <PaperAirplaneIcon className="w-4 h-4" />
                  </button>
                </form>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex flex-col md:flex-row md:items-end md:space-x-4 space-y-3 md:space-y-0">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company (optional for web signals)</label>
                  <input
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="e.g., Airbnb"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={runInvestmentAnalysis}
                  disabled={investLoading || Object.keys(documents).length === 0}
                  className="px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300"
                >
                  {investLoading ? 'Analyzing…' : 'Run Investment Analysis'}
                </button>
              </div>

              <div className="mt-4 text-xs text-gray-500">
                Uses your RAG context (Pathway + Memory) and Friendly AI, tailored to the selected persona.
              </div>
            </div>

            {investResult && (
              <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="text-lg font-semibold">Decision</div>
                  <span className={
                    investResult.decision === 'invest'
                      ? 'px-3 py-1 rounded-full text-xs bg-green-50 text-green-700 border border-green-200'
                      : investResult.decision === 'defer'
                      ? 'px-3 py-1 rounded-full text-xs bg-yellow-50 text-yellow-700 border border-yellow-200'
                      : investResult.decision === 'insufficient_data'
                      ? 'px-3 py-1 rounded-full text-xs bg-gray-50 text-gray-700 border border-gray-200'
                      : 'px-3 py-1 rounded-full text-xs bg-red-50 text-red-700 border border-red-200'
                  }>
                    {investResult.decision.replace('_', ' ')}
                  </span>
                </div>

                <LikelihoodBar value={investResult.likelihood_percent} />

                <div>
                  <div className="text-sm font-semibold mb-1">Rationale</div>
                  <div className="text-sm text-gray-800">{investResult.rationale}</div>
                </div>

                <div>
                  <div className="text-sm font-semibold mb-1">3 points to watch</div>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-gray-800">
                    {investResult.forecast_points.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {!investResult && !investLoading && (
              <div className="text-gray-500 text-sm">
                Run an analysis to see the likelihood score and investment summary.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
