import { AxisKind } from "../types/workflow";

export const getAxisLabel = (kind: AxisKind): string => {
    switch (kind) {
        case "strategy":
            return "Strategy";
        case "cell_line":
            return "Biobanking";
        case "stressor":
            return "Cell Models";
        case "perturbation":
            return "Functional Genomics";
        case "measurement":
            return "PST";
        case "analysis":
            return "Compute";
        case "program":
            return "Senior Steering Committee";
        default:
            return kind;
    }
};
