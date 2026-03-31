import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import axios from 'axios';

/**
 * Upload page - Allows users to upload PDFs for processing
 * Features:
 * - Drag and drop file upload
 * - File validation
 * - Upload progress tracking
 * - Error handling
 */
export function Upload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileSelect = (selectedFile) => {
    // Validate file type and size
    if (!selectedFile.type.includes('pdf')) {
      setError('Please select a PDF file');
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) { // 50MB limit
      setError('File size must be less than 50MB');
      return;
    }
    setFile(selectedFile);
    setError(null);
    setSuccess(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('bg-blue-50', 'border-blue-400');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('bg-blue-50', 'border-blue-400');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('bg-blue-50', 'border-blue-400');
    if (e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('/api/pdfs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          setUploadProgress(progress);
        }
      });

      setSuccess(true);
      setFile(null);
      setUploadProgress(0);
      
      // Redirect to learning page after 2 seconds
      setTimeout(() => {
        window.location.href = `/learn/${res.data.session_id}`;
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6"
    >
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900">Upload Your Learning Material</h1>
          <p className="text-slate-600 mt-2">Submit a PDF and we'll extract key concepts and generate quizzes</p>
        </div>

        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-lg shadow-lg p-8"
        >
          {/* Drag and Drop Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className="border-2 border-dashed border-slate-300 rounded-lg p-12 text-center transition cursor-pointer hover:border-blue-400 hover:bg-blue-50"
          >
            <div className="text-5xl mb-4">📄</div>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              Drag and drop your PDF here
            </h3>
            <p className="text-slate-500 mb-6">or</p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-6 rounded-lg transition"
            >
              Browse Files
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
              className="hidden"
            />
            <p className="text-slate-500 text-sm mt-4">
              Maximum file size: 50MB
            </p>
          </div>

          {/* Selected File Display */}
          {file && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-slate-900">{file.name}</p>
                  <p className="text-sm text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-red-500 hover:text-red-700 font-medium"
                >
                  Remove
                </button>
              </div>
            </motion.div>
          )}

          {/* Error Display */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg"
            >
              {error}
            </motion.div>
          )}

          {/* Success Display */}
          {success && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-6 p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg"
            >
              ✓ Upload successful! Redirecting...
            </motion.div>
          )}

          {/* Progress Bar */}
          {uploading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-6"
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-slate-900">Uploading...</p>
                <p className="text-sm text-slate-500">{uploadProgress}%</p>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${uploadProgress}%` }}
                  transition={{ duration: 0.3 }}
                  className="bg-blue-500 h-2 rounded-full"
                ></motion.div>
              </div>
            </motion.div>
          )}

          {/* Upload Button */}
          {file && !uploading && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleUpload}
              className="w-full mt-8 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-bold py-3 px-6 rounded-lg transition shadow-lg"
            >
              Upload and Process
            </motion.button>
          )}

          {/* Info Box */}
          <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-semibold text-slate-900 mb-2">What happens next?</h4>
            <ul className="text-sm text-slate-700 space-y-1">
              <li>✓ We'll extract key concepts from your PDF</li>
              <li>✓ Generate adaptive quizzes based on the content</li>
              <li>✓ Track your learning progress with spaced repetition</li>
              <li>✓ Provide personalized recommendations</li>
            </ul>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

export default Upload;
