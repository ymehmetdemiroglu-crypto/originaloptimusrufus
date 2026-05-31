import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Calculator from './Calculator.jsx';
import './App.css';

const Landing = React.lazy(() => import('./Landing'));
const Results = React.lazy(() => import('./Results'));
const Profile = React.lazy(() => import('./Profile'));

function PageSkeleton() {
  return (
    <div className="min-h-screen bg-[#080a0e] text-[#f8f9fa] flex flex-col items-center justify-center p-6 font-sans relative overflow-hidden">
      {/* Background Ambience matches index.css */}
      <div className="absolute inset-0 bg-radial-gradient(ellipse 80% 60% at 50% -20%, rgba(255, 159, 0, 0.06), transparent 70%) pointer-events-none z-0"></div>
      
      <div className="w-full max-w-4xl p-8 rounded-2xl bg-gradient-to-br from-[#14161c]/80 to-[#0a0b0e]/95 border border-white/[0.03] backdrop-blur-xl shadow-2xl animate-pulse space-y-8 z-10 relative">
        <div className="h-8 bg-white/[0.04] border border-white/[0.02] rounded-lg w-1/3"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-32 bg-white/[0.04] border border-white/[0.02] rounded-xl"></div>
          <div className="h-32 bg-white/[0.04] border border-white/[0.02] rounded-xl"></div>
          <div className="h-32 bg-white/[0.04] border border-white/[0.02] rounded-xl"></div>
        </div>
        <div className="h-48 bg-white/[0.04] border border-white/[0.02] rounded-xl"></div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/calculator" element={<Calculator />} />
          <Route path="/results" element={<Results />} />
          <Route path="/profile/:id" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
