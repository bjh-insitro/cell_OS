export type AxisKind = "cell_line" | "stressor" | "perturbation" | "measurement";

export type AxisStatus = "not_started" | "design" | "in_progress" | "blocked" | "ready";

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
}

export interface Workflow {
    id: string;
    name: string;
    description: string;
    owner: string;
    status: AxisStatus;
    axes: WorkflowAxis[];
}
