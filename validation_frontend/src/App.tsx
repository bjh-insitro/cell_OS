import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import PoshA549StatusPage from './pages/PoshA549StatusPage';
import GlobalDependencyMapPage from './pages/GlobalDependencyMapPage';
import LandingPage from './pages/LandingPage';
import UnderDevelopmentPage from './pages/UnderDevelopmentPage';
import CellThalamusPage from './pages/CellThalamus/CellThalamusPage';
import ViewingPage from './pages/CellThalamus/ViewingPage';
import AutonomousLoopPage from './pages/AutonomousLoopPage';
import EpistemicProvenancePage from './pages/EpistemicProvenancePageNew';
import EpistemicDocumentaryPage from './pages/EpistemicDocumentaryPage';
import CalibrationPlatePage from './pages/CalibrationPlatePage';
import CalibrationResultsPage from './pages/CalibrationResultsPage';
import CalibrationResultsLoaderPage from './pages/CalibrationResultsLoaderPage';
import PlateDesignComparisonPage from './pages/PlateDesignComparisonPage';

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/dashboard" element={<PoshA549StatusPage />} />
                <Route path="/map" element={<GlobalDependencyMapPage />} />
                <Route path="/cell-thalamus" element={<CellThalamusPage />} />
                <Route path="/cell-thalamus/viewing" element={<ViewingPage />} />
                <Route path="/autonomous-loop" element={<AutonomousLoopPage />} />
                <Route path="/epistemic-provenance" element={<EpistemicProvenancePage />} />
                <Route path="/documentary" element={<EpistemicDocumentaryPage />} />
                <Route path="/calibration-plate" element={<CalibrationPlatePage />} />
                <Route path="/calibration-results/:plateId" element={<CalibrationResultsPage />} />
                <Route path="/calibration-results-loader/:plateId" element={<CalibrationResultsLoaderPage />} />
                <Route path="/plate-design-comparison" element={<PlateDesignComparisonPage />} />
                <Route path="/under-development" element={<UnderDevelopmentPage />} />
            </Routes>
        </Router>
    );
}

export default App;
