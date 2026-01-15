export type AxisKind = "strategy" | "cell_line" | "stressor" | "perturbation" | "measurement" | "analysis" | "container" | "program";

export type AxisStatus = "not_started" | "design" | "in_progress" | "blocked" | "ready" | "done";

export type TaskStatus = "not_started" | "in_progress" | "blocked" | "done";

export interface AxisTask {
    id: string;
    title: string;
    status: TaskStatus;
}

export type DependencyStatus = "ready" | "pending" | "blocked" | "not_started";

export interface Dependency {
    id: string;
    label: string;
    status: DependencyStatus;
    linkedAxisId?: string;
}

export interface SubItem {
    title: string;
    status: string;
}

export interface WorkflowAxis {
    id: string;
    kind: AxisKind;
    name: string;
    status: AxisStatus;
    owner: string;
    definitionOfDone: string;
    inputsRequired: string;
    outputsPromised: string;
    blockers?: string[];
    benchlingEntityId?: string;
    tasks: AxisTask[];
    dependencies?: Dependency[];
    visible?: boolean;
    subItems?: SubItem[];
    quarter?: number; // 0-4 for timeline positioning (0 = Q1 2026, 1 = Q2 2026, etc.)
    program?: string; // Program filter (e.g., 'rubric', 'cell_thalamus', 'data_printing')
}

export interface Workflow {
    id: string;
    name: string;
    description: string;
    owner: string;
    status: AxisStatus;
    axes: WorkflowAxis[];
}
