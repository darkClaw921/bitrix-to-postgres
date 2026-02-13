import type { Components } from 'react-markdown'

export const markdownTableComponents: Components = {
  table: ({ children, ...props }) => (
    <table
      style={{ borderCollapse: 'collapse', width: '100%', margin: '1em 0' }}
      {...props}
    >
      {children}
    </table>
  ),
  thead: ({ children, ...props }) => (
    <thead style={{ backgroundColor: '#f9fafb' }} {...props}>
      {children}
    </thead>
  ),
  th: ({ children, ...props }) => (
    <th
      style={{
        border: '1px solid #d1d5db',
        padding: '8px 12px',
        textAlign: 'left',
        fontWeight: 600,
        fontSize: '0.875rem',
      }}
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td
      style={{
        border: '1px solid #d1d5db',
        padding: '8px 12px',
        fontSize: '0.875rem',
      }}
      {...props}
    >
      {children}
    </td>
  ),
}
