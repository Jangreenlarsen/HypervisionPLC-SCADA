// Signalveje i Tegn (v4.2.0, PLAN.md › Signalvej): find rørvejen mellem to symboler ud fra tegningens forbindelser og
// beregn, hvilke dele der skal have løbelys og i hvilken retning. Rene beregninger på grafen fra scada-core
// `connectionGraph()` — testet i signalPath.test.ts. Gemmes af backend (services/signal_paths.py).
// Delt i signalpath/ (graph, flow, route, net, answers) i v4.15.1; denne fil samler dem, så imports er uændrede.

export * from './signalpath/graph';
export * from './signalpath/flow';
export * from './signalpath/route';
export * from './signalpath/net';
export * from './signalpath/answers';
