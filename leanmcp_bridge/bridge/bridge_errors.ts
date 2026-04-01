export class PythonBridgeError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'PythonBridgeError';
    }
}

export class PythonBridgeLaunchError extends PythonBridgeError {
    constructor(message: string) {
        super(message);
        this.name = 'PythonBridgeLaunchError';
    }
}

export class PythonBridgeParseError extends PythonBridgeError {
    constructor(message: string) {
        super(message);
        this.name = 'PythonBridgeParseError';
    }
}