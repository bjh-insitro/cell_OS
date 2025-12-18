import React from "react";
import { WorkflowAxis } from "../types/workflow";
import { AxisCard } from "./AxisCard";

interface AxisGridProps {
    axes: WorkflowAxis[];
    selectedAxisId?: string;
    onAxisSelect: (axisId: string) => void;
}

export const AxisGrid: React.FC<AxisGridProps> = ({ axes, selectedAxisId, onAxisSelect }) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {axes.map((axis) => (
                <AxisCard
                    key={axis.id}
                    axis={axis}
                    isSelected={axis.id === selectedAxisId}
                    onClick={onAxisSelect}
                />
            ))}
        </div>
    );
};
