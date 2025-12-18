import React from 'react';
import { Link } from 'react-router-dom';

const UnderDevelopmentPage: React.FC = () => {
    return (
        <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4">
            <div className="text-center">
                <h1 className="text-4xl font-bold text-white mb-4">Under Development</h1>
                <p className="text-slate-400 text-lg mb-8">
                    The selected experimental configuration is not yet available.
                </p>
                <Link
                    to="/"
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors"
                >
                    Return to Selection
                </Link>
            </div>
        </div>
    );
};

export default UnderDevelopmentPage;
