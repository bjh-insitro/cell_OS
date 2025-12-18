import { AxisKind } from "../types/workflow";

export const getAxisLabel = (kind: AxisKind): string => {
    switch (kind) {
        case "cell_line":
            return "Biobanking";
        case "stressor":
            return "Cell Models";
        case "perturbation":
            return "Functional Genomics";
        case "measurement":
            return "PST";
        default:
            return kind;
    }
};
