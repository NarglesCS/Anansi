import React, { useEffect, useMemo, useState } from 'react';

type GraphQLErrorShape = {
  message: string;
  locations?: Array<{ line: number; column: number }>;
  path?: Array<string | number>;
};

type GraphQLResponse = {
  data?: unknown;
  errors?: GraphQLErrorShape[];
};

type OperationMode = 'query' | 'mutation';
type Status = 'idle' | 'loading' | 'success' | 'error';

type SchemaView = {
  queryType: string | null;
  mutationType: string | null;
  types: Array<{
    name: string;
    kind: string;
    description?: string | null;
    fields?: Array<{
      name: string;
      description?: string | null;
      type: string;
      args: Array<{ name: string; type: string }>;
    }>;
    enumValues?: string[];
    inputFields?: Array<{ name: string; type: string }>;
  }>;
};

const defaultEndpoint = 'http://127.0.0.1:8000/graphql';
const defaultQuery = `query BlogOverview($role: Role, $limit: Int) {
  users(role: $role, limit: $limit) {
    id
    name
    role
    posts(limit: 2) {
      id
      title
      published
      comments(limit: 2) {
        id
        text
        author {
          name
        }
      }
    }
  }
}`;
const defaultMutation = `mutation CreateDraft($input: CreatePostInput!) {
  createPost(input: $input) {
    id
    title
    published
    author {
      name
    }
  }
}`;
const defaultVariables = `{
  "role": "ADMIN",
  "limit": 3
}`;
const defaultMutationVariables = `{
  "input": {
    "authorId": "u3",
    "title": "Hello from the UI",
    "body": "Created via the Anansi GraphQL UI"
  }
}`;

const introspectionQuery = `query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          type {
            ...TypeRef
          }
        }
        type {
          ...TypeRef
        }
      }
      inputFields {
        name
        type {
          ...TypeRef
        }
      }
      enumValues(includeDeprecated: true) {
        name
      }
    }
  }
}
fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
        }
      }
    }
  }
}`;

function formatType(type: any): string {
  if (!type) return 'Unknown';
  if (type.kind === 'NON_NULL') {
    return `${formatType(type.ofType)}!`;
  }
  if (type.kind === 'LIST') {
    return `[${formatType(type.ofType)}]`;
  }
  return type.name ?? 'Unknown';
}

function normalizeSchema(payload: any): SchemaView {
  const schema = payload?.data?.__schema;
  const visibleTypes = (schema?.types ?? []).filter(
    (type: any) => type.name && !type.name.startsWith('__')
  );
  return {
    queryType: schema?.queryType?.name ?? null,
    mutationType: schema?.mutationType?.name ?? null,
    types: visibleTypes
      .map((type: any) => ({
        name: type.name,
        kind: type.kind,
        description: type.description,
        fields: (type.fields ?? []).map((field: any) => ({
          name: field.name,
          description: field.description,
          type: formatType(field.type),
          args: (field.args ?? []).map((arg: any) => ({
            name: arg.name,
            type: formatType(arg.type)
          }))
        })),
        enumValues: (type.enumValues ?? []).map((value: any) => value.name),
        inputFields: (type.inputFields ?? []).map((field: any) => ({
          name: field.name,
          type: formatType(field.type)
        }))
      }))
      .sort((a: SchemaView["types"][number], b: SchemaView["types"][number]) => a.name.localeCompare(b.name))
  };
}

async function postGraphQL(endpoint: string, query: string, variables?: unknown): Promise<GraphQLResponse> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query, variables })
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (!response.ok) {
    return {
      data: payload?.data,
      errors: payload?.errors ?? [{ message: `HTTP ${response.status}: ${response.statusText}` }]
    };
  }

  return payload;
}

function App() {
  const [endpoint, setEndpoint] = useState(defaultEndpoint);
  const [operationMode, setOperationMode] = useState<OperationMode>('query');
  const [queryText, setQueryText] = useState(defaultQuery);
  const [mutationText, setMutationText] = useState(defaultMutation);
  const [queryVariables, setQueryVariables] = useState(defaultVariables);
  const [mutationVariables, setMutationVariables] = useState(defaultMutationVariables);
  const [status, setStatus] = useState<Status>('idle');
  const [result, setResult] = useState<GraphQLResponse | null>(null);
  const [schemaStatus, setSchemaStatus] = useState<Status>('idle');
  const [schemaResult, setSchemaResult] = useState<SchemaView | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [endpointHelpOpen, setEndpointHelpOpen] = useState(true);

  const activeOperationText = operationMode === 'query' ? queryText : mutationText;
  const activeVariablesText = operationMode === 'query' ? queryVariables : mutationVariables;

  const parsedVariables = useMemo(() => {
    if (!activeVariablesText.trim()) return {};
    return JSON.parse(activeVariablesText);
  }, [activeVariablesText]);

  const executeOperation = async () => {
    try {
      setStatus('loading');
      const payload = await postGraphQL(endpoint, activeOperationText, parsedVariables);
      setResult(payload);
      setStatus(payload.errors?.length ? 'error' : 'success');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setResult({ errors: [{ message }] });
      setStatus('error');
    }
  };

  const loadSchema = async () => {
    try {
      setSchemaStatus('loading');
      setSchemaError(null);
      const payload = await postGraphQL(endpoint, introspectionQuery, {});
      if (payload.errors?.length) {
        setSchemaResult(null);
        setSchemaStatus('error');
        setSchemaError(payload.errors.map((error) => error.message).join('\n'));
        return;
      }
      setSchemaResult(normalizeSchema(payload));
      setSchemaStatus('success');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setSchemaResult(null);
      setSchemaStatus('error');
      setSchemaError(message);
    }
  };

  useEffect(() => {
    void loadSchema();
  }, []);

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Anansi GraphQL UI</p>
          <h1>Explore the mock blog graph in your browser.</h1>
          <p className="hero-copy">
            Write queries or mutations, pass variables, inspect the schema, and view formatted JSON results.
          </p>
        </div>
        <button className="secondary-button" onClick={() => void loadSchema()} disabled={schemaStatus === 'loading'}>
          {schemaStatus === 'loading' ? 'Refreshing schema…' : 'Refresh schema'}
        </button>
      </header>

      <section className="endpoint-card">
        <div className="endpoint-row">
          <label htmlFor="endpoint">GraphQL HTTP endpoint</label>
          <input
            id="endpoint"
            value={endpoint}
            onChange={(event) => setEndpoint(event.target.value)}
            placeholder="http://127.0.0.1:8000/graphql"
          />
        </div>
        <button className="link-button" onClick={() => setEndpointHelpOpen((open) => !open)}>
          {endpointHelpOpen ? 'Hide setup hints' : 'Show setup hints'}
        </button>
        {endpointHelpOpen ? (
          <div className="callout">
            <p>
              Anansi&apos;s MCP server is stdio-based, so this UI expects a separate HTTP GraphQL endpoint that exposes the same schema.
              Point this field at that endpoint or place a small proxy in front of Anansi.
            </p>
            <ul>
              <li>Default expectation: <code>http://127.0.0.1:8000/graphql</code></li>
              <li>Mutations require the backing server to enable writes.</li>
              <li>The seed data includes users, posts, and comments.</li>
            </ul>
          </div>
        ) : null}
      </section>

      <main className="workspace-grid">
        <section className="panel editor-panel">
          <div className="panel-header">
            <h2>Operation editor</h2>
            <div className="segmented-control">
              <button
                className={operationMode === 'query' ? 'is-active' : ''}
                onClick={() => setOperationMode('query')}
              >
                Query
              </button>
              <button
                className={operationMode === 'mutation' ? 'is-active' : ''}
                onClick={() => setOperationMode('mutation')}
              >
                Mutation
              </button>
            </div>
          </div>

          <label className="stacked-field">
            <span>{operationMode === 'query' ? 'GraphQL query' : 'GraphQL mutation'}</span>
            <textarea
              value={operationMode === 'query' ? queryText : mutationText}
              onChange={(event) =>
                operationMode === 'query'
                  ? setQueryText(event.target.value)
                  : setMutationText(event.target.value)
              }
              rows={18}
              spellCheck={false}
            />
          </label>

          <label className="stacked-field">
            <span>Variables (JSON)</span>
            <textarea
              value={operationMode === 'query' ? queryVariables : mutationVariables}
              onChange={(event) =>
                operationMode === 'query'
                  ? setQueryVariables(event.target.value)
                  : setMutationVariables(event.target.value)
              }
              rows={10}
              spellCheck={false}
            />
          </label>

          <div className="action-row">
            <button className="primary-button" onClick={() => void executeOperation()} disabled={status === 'loading'}>
              {status === 'loading' ? 'Running…' : `Run ${operationMode}`}
            </button>
            <span className={`status-pill status-${status}`}>{status}</span>
          </div>
        </section>

        <section className="panel results-panel">
          <div className="panel-header">
            <h2>Result</h2>
            <span className="muted">Formatted JSON response</span>
          </div>
          <pre>{result ? JSON.stringify(result, null, 2) : 'Run a query or mutation to see the response here.'}</pre>
        </section>

        <section className="panel schema-panel">
          <div className="panel-header">
            <h2>Schema browser</h2>
            <span className="muted">
              {schemaResult?.queryType ? `Query: ${schemaResult.queryType}` : 'No schema loaded'}
              {schemaResult?.mutationType ? ` · Mutation: ${schemaResult.mutationType}` : ''}
            </span>
          </div>
          {schemaError ? <p className="error-banner">{schemaError}</p> : null}
          <div className="schema-list">
            {schemaResult?.types.map((type) => (
              <details key={type.name} open={type.name === schemaResult.queryType || type.name === schemaResult.mutationType}>
                <summary>
                  <span>{type.name}</span>
                  <span className="muted">{type.kind}</span>
                </summary>
                {type.description ? <p>{type.description}</p> : null}
                {type.fields?.length ? (
                  <ul>
                    {type.fields.map((field) => (
                      <li key={field.name}>
                        <code>{field.name}</code>
                        {field.args.length ? (
                          <span>
                            (
                            {field.args.map((arg) => `${arg.name}: ${arg.type}`).join(', ')}
                            )
                          </span>
                        ) : null}
                        <span>: {field.type}</span>
                        {field.description ? <p>{field.description}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {type.inputFields?.length ? (
                  <ul>
                    {type.inputFields.map((field) => (
                      <li key={field.name}>
                        <code>{field.name}</code>: {field.type}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {type.enumValues?.length ? <p>Values: {type.enumValues.join(', ')}</p> : null}
              </details>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
