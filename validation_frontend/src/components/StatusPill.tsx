import React from "react";
import { AxisStatus, TaskStatus, DependencyStatus } from "../types/workflow";

type StatusType = AxisStatus | TaskStatus | DependencyStatus;

interface StatusPillProps {
    status: StatusType;
    className?: string;
}

const getStatusColor = (status: StatusType) => {
    switch (status) {
        case "not_started":
        case "pending":
            return "bg-slate-100 text-slate-600";
        case "design":
            return "bg-amber-100 text-amber-700";
        case "in_progress":
            return "bg-blue-100 text-blue-700";
        case "blocked":
            return "bg-red-100 text-red-700";
        case "ready":
        case "done":
            return "bg-green-100 text-green-700";
        default:
            return "bg-slate-100 text-slate-600";
    }
};

const formatStatus = (status: StatusType) => {
    return status.replace(/_/g, " ");
};

export const StatusPill: React.FC<StatusPillProps> = ({ status, className = "" }) => {
    return (
        <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusColor(
                status
            )} ${className}`}
        >
            {formatStatus(status)}
        </span>
    );
};
