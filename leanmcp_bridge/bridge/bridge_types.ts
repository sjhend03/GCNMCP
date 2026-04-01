export type PythonBridgeRequest = {
    tool: string;
    agruments?: Record<string, unknown>;
}

export type PythonBridgeSuccess = {
    ok: true;
    result: unknown;
}

export type PythonBridgeFailure = {
    ok: false;
    error: string;
}

export type PythonBridgeResponse = PythonBridgeSuccess | PythonBridgeFailure;