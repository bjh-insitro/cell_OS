import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import PoshA549StatusPage from './pages/PoshA549StatusPage';
import MenadioneStatusPage from './pages/MenadioneStatusPage';
import MenadioneMapPage from './pages/MenadioneMapPage';
import OverallMapPage from './pages/OverallMapPage';
import GlobalDependencyMapPage from './pages/GlobalDependencyMapPage';
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

const basename = import.meta.env.BASE_URL;

function App() {
    return (
        <Router basename={basename}>
            <Routes>
                <Route path="/" element={<PoshA549StatusPage />} />
                <Route path="/menadione" element={<MenadioneStatusPage />} />
                <Route path="/menadione/map" element={<MenadioneMapPage />} />
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
                <Route path="/map" element={<GlobalDependencyMapPage />} />
                <Route path="/overall" element={<OverallMapPage />} />
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
