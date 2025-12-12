import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import PoshA549StatusPage from './pages/PoshA549StatusPage';
import GlobalDependencyMapPage from './pages/GlobalDependencyMapPage';
import LandingPage from './pages/LandingPage';
import UnderDevelopmentPage from './pages/UnderDevelopmentPage';
import CellThalamusPage from './pages/CellThalamus/CellThalamusPage';

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/dashboard" element={<PoshA549StatusPage />} />
                <Route path="/map" element={<GlobalDependencyMapPage />} />
                <Route path="/cell-thalamus" element={<CellThalamusPage />} />
                <Route path="/under-development" element={<UnderDevelopmentPage />} />
            </Routes>
        </Router>
    );
}

export default App;
