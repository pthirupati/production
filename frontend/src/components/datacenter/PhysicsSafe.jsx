import { Component } from 'react'

/**
 * Isolates @react-three/rapier WASM/Physics failures so the 3D hall keeps
 * rendering with non-physics animation (no whole-scene Twin3DSafe trip).
 */
export default class PhysicsSafe extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { failed: true, error }
  }

  componentDidCatch(error, info) {
    console.error('Rapier Physics failed — continuing without physics', error, info)
    try { this.props.onFail?.(error) } catch { /* ignore */ }
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback ?? null
    }
    return this.props.children
  }
}
