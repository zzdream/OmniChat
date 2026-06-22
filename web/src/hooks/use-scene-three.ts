import {
  AmbientLight,
  Box3,
  BoxHelper,
  Color,
  DirectionalLight,
  GridHelper,
  Group,
  Material,
  Mesh,
  Object3D,
  PerspectiveCamera,
  Raycaster,
  Scene,
  SRGBColorSpace,
  Texture,
  Vector2,
  Vector3,
  WebGLRenderer
} from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { SCENE_MAX_GLB_BYTES } from '@/constants/scene'
import type { LoadedSceneObject, SceneActionPayload, SceneObjectSnapshot } from '@/types/scene'

const decoderBase = `${import.meta.env.BASE_URL}`.replace(/\/$/, '')

let gltfLoader: GLTFLoader | null = null
let ktx2Loader: KTX2Loader | null = null
let dracoLoader: DRACOLoader | null = null
let gltfLoaderInit: Promise<GLTFLoader> | null = null

/**
 * 完整 GLTF 加载器：Meshopt + KTX2(Basis) + Draco
 * simrender 导出的 bus.glb 等模型需要 KTX2。
 */
async function ensureGltfLoader(renderer: WebGLRenderer): Promise<GLTFLoader> {
  if (gltfLoader) {
    ktx2Loader?.detectSupport(renderer)
    return gltfLoader
  }

  if (!gltfLoaderInit) {
    gltfLoaderInit = (async () => {
      await MeshoptDecoder.ready

      ktx2Loader = new KTX2Loader()
      ktx2Loader.setTranscoderPath(`${decoderBase}/basis/`)
      ktx2Loader.detectSupport(renderer)

      dracoLoader = new DRACOLoader()
      dracoLoader.setDecoderPath(`${decoderBase}/draco/gltf/`)

      const loader = new GLTFLoader()
      loader.setKTX2Loader(ktx2Loader)
      loader.setDRACOLoader(dracoLoader)
      loader.setMeshoptDecoder(MeshoptDecoder)
      gltfLoader = loader
      return loader
    })()
  }

  return gltfLoaderInit
}

function createId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000
}

function toSnapshot(object: LoadedSceneObject): SceneObjectSnapshot {
  const { x, y, z } = object.root.position
  const rot = object.root.rotation
  const scale = object.root.scale
  return {
    id: object.id,
    name: object.name,
    fileName: object.fileName,
    position: { x: round3(x), y: round3(y), z: round3(z) },
    rotation: {
      x: round3((rot.x * 180) / Math.PI),
      y: round3((rot.y * 180) / Math.PI),
      z: round3((rot.z * 180) / Math.PI)
    },
    scale: { x: round3(scale.x), y: round3(scale.y), z: round3(scale.z) }
  }
}

export function useSceneThree() {
  const containerRef = shallowRef<HTMLElement | null>(null)
  const objects = ref<LoadedSceneObject[]>([])
  const selectedObjectId = ref<string | null>(null)
  const loading = ref(false)
  const loadError = ref('')
  const isReady = ref(false)

  let scene: Scene | null = null
  let camera: PerspectiveCamera | null = null
  let renderer: WebGLRenderer | null = null
  let controls: OrbitControls | null = null
  let modelsGroup: Group | null = null
  let animationId = 0
  let resizeObserver: ResizeObserver | null = null

  const raycaster = new Raycaster()
  const pointer = new Vector2()
  let selectionHelper: BoxHelper | null = null
  let pointerDown = { x: 0, y: 0 }
  const CLICK_DRAG_THRESHOLD = 6

  const selectedObject = computed(
    () => objects.value.find(item => item.id === selectedObjectId.value) ?? null
  )

  const objectSnapshots = computed(() => objects.value.map(toSnapshot))

  function prepareLoadedModel(root: Object3D) {
    root.traverse((child: Object3D) => {
      if (!(child instanceof Mesh)) return
      child.castShadow = false
      child.receiveShadow = false
      child.frustumCulled = false

      const materials = Array.isArray(child.material) ? child.material : [child.material]
      for (const material of materials) {
        if (!material) continue
        const maps = [
          (material as Material & { map?: Texture }).map,
          (material as Material & { emissiveMap?: Texture }).emissiveMap,
          (material as Material & { normalMap?: Texture }).normalMap,
          (material as Material & { roughnessMap?: Texture }).roughnessMap,
          (material as Material & { metalnessMap?: Texture }).metalnessMap
        ]
        for (const map of maps) {
          if (map) map.colorSpace = SRGBColorSpace
        }
        material.needsUpdate = true
      }
    })
  }

  function clearHighlight() {
    if (selectionHelper && scene) {
      scene.remove(selectionHelper)
      selectionHelper.geometry.dispose()
      selectionHelper = null
    }
  }

  function applyHighlight(objectId: string) {
    clearHighlight()
    const target = objects.value.find(item => item.id === objectId)
    if (!target || !scene) return

    selectionHelper = new BoxHelper(target.root, 0x6366f1)
    scene.add(selectionHelper)
    selectedObjectId.value = objectId
  }

  function renderFrame() {
    if (!renderer || !scene || !camera) return
    selectionHelper?.update()
    controls?.update()
    renderer.render(scene, camera)
  }

  function startLoop() {
    const loop = () => {
      animationId = requestAnimationFrame(loop)
      renderFrame()
    }
    loop()
  }

  function handleResize() {
    const container = containerRef.value
    if (!container || !camera || !renderer) return
    const width = container.clientWidth
    const height = container.clientHeight
    if (width <= 0 || height <= 0) return
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    renderer.setSize(width, height)
    renderFrame()
  }

  function disposeObject(object: LoadedSceneObject) {
    if (selectedObjectId.value === object.id) {
      clearHighlight()
    }

    object.root.traverse((child: Object3D) => {
      if (!(child instanceof Mesh)) return
      child.geometry?.dispose()
      const materials = Array.isArray(child.material) ? child.material : [child.material]
      for (const material of materials) {
        if (!material) continue
        for (const key of Object.keys(material) as (keyof Material)[]) {
          const value = material[key]
          if (value instanceof Texture) value.dispose()
        }
        material.dispose()
      }
    })

    object.root.removeFromParent()
  }

  function removeObject(objectId: string) {
    const index = objects.value.findIndex(item => item.id === objectId)
    if (index === -1) return

    if (selectedObjectId.value === objectId) {
      clearHighlight()
      selectedObjectId.value = null
    }

    const [removed] = objects.value.splice(index, 1)
    disposeObject(removed)

    if (!selectedObjectId.value && objects.value.length) {
      applyHighlight(objects.value[0].id)
    }

    renderFrame()
  }

  function initScene(container: HTMLElement) {
    if (scene) return

    containerRef.value = container
    scene = new Scene()
    scene.background = new Color('#0f1117')

    const width = container.clientWidth || 640
    const height = container.clientHeight || 480
    camera = new PerspectiveCamera(50, width / height, 0.1, 1000)
    camera.position.set(4, 3, 6)

    renderer = new WebGLRenderer({ antialias: true, alpha: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(width, height)
    renderer.outputColorSpace = SRGBColorSpace
    container.appendChild(renderer.domElement)

    controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.target.set(0, 0.5, 0)

    const ambient = new AmbientLight(0xffffff, 0.8)
    const directional = new DirectionalLight(0xffffff, 2)
    directional.position.set(5, 10, 7)
    scene.add(ambient, directional)

    const grid = new GridHelper(20, 20, '#334155', '#1e293b')
    scene.add(grid)

    modelsGroup = new Group()
    modelsGroup.name = 'models-root'
    scene.add(modelsGroup)

    renderer.domElement.addEventListener('pointerdown', handlePointerDown)
    renderer.domElement.addEventListener('click', handleCanvasClick)

    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(container)

    isReady.value = true
    void ensureGltfLoader(renderer)
    startLoop()
    renderFrame()
  }

  function destroyScene() {
    cancelAnimationFrame(animationId)
    resizeObserver?.disconnect()
    resizeObserver = null

    dracoLoader?.dispose()
    dracoLoader = null
    ktx2Loader?.dispose()
    ktx2Loader = null
    gltfLoader = null
    gltfLoaderInit = null

    if (renderer) {
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown)
      renderer.domElement.removeEventListener('click', handleCanvasClick)
      renderer.dispose()
      renderer.domElement.remove()
    }

    for (const item of objects.value) disposeObject(item)
    objects.value = []
    selectedObjectId.value = null

    controls?.dispose()
    scene = null
    camera = null
    renderer = null
    controls = null
    modelsGroup = null
    containerRef.value = null
    isReady.value = false
  }

  function findObjectFromNode(node: Object3D): LoadedSceneObject | null {
    let current: Object3D | null = node
    while (current) {
      const sceneId = current.userData?.sceneObjectId as string | undefined
      if (sceneId) {
        return objects.value.find(item => item.id === sceneId) ?? null
      }
      if (current === modelsGroup) break
      current = current.parent
    }
    return null
  }

  function pickObjectAt(clientX: number, clientY: number): LoadedSceneObject | null {
    const container = containerRef.value
    if (!container || !camera || !modelsGroup?.children.length) return null

    const rect = container.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return null

    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1

    raycaster.setFromCamera(pointer, camera)
    const hits = raycaster.intersectObjects(modelsGroup.children, true)
    for (const hit of hits) {
      const matched = findObjectFromNode(hit.object)
      if (matched) return matched
    }
    return null
  }

  function handlePointerDown(event: PointerEvent) {
    pointerDown = { x: event.clientX, y: event.clientY }
  }

  function handleCanvasClick(event: MouseEvent) {
    const moved = Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y)
    if (moved > CLICK_DRAG_THRESHOLD) return

    const matched = pickObjectAt(event.clientX, event.clientY)
    if (!matched) {
      selectedObjectId.value = null
      clearHighlight()
      return
    }

    applyHighlight(matched.id)
  }

  async function loadGlbFile(file: File) {
    loadError.value = ''
    if (!file.name.toLowerCase().endsWith('.glb') && !file.name.toLowerCase().endsWith('.gltf')) {
      loadError.value = '仅支持 .glb / .gltf 文件'
      return
    }
    if (file.size > SCENE_MAX_GLB_BYTES) {
      loadError.value = '文件过大，请上传小于 50MB 的模型'
      return
    }
    if (!modelsGroup) {
      loadError.value = '3D 场景尚未初始化'
      return
    }
    if (!renderer) {
      loadError.value = '3D 渲染器尚未就绪'
      return
    }

    loading.value = true
    const objectUrl = URL.createObjectURL(file)

    try {
      const loader = await ensureGltfLoader(renderer)
      const gltf = await loader.loadAsync(objectUrl)
      const root = gltf.scene
      const baseName = file.name.replace(/\.(glb|gltf)$/i, '')
      root.name = baseName
      prepareLoadedModel(root)

      const box = new Box3().setFromObject(root)
      const size = box.getSize(new Vector3())
      const center = box.getCenter(new Vector3())
      root.position.sub(center)
      root.position.y += size.y / 2

      const maxDim = Math.max(size.x, size.y, size.z, 0.001)
      if (maxDim > 4) {
        const scale = 2 / maxDim
        root.scale.setScalar(scale)
      }

      const id = createId('model')
      root.traverse((child: Object3D) => {
        child.userData.sceneObjectId = id
      })
      modelsGroup.add(root)

      const displayName = baseName || file.name
      objects.value.push({
        id,
        name: displayName,
        fileName: file.name,
        root
      })

      selectObject(id)
    } catch (err) {
      const detail = err instanceof Error ? err.message : '未知错误'
      loadError.value = `模型加载失败：${file.name}（${detail}）`
    } finally {
      URL.revokeObjectURL(objectUrl)
      loading.value = false
    }
  }

  function selectObject(objectId: string) {
    applyHighlight(objectId)
    focusObject(objectId)
  }

  function focusObject(objectId: string) {
    const target = objects.value.find(item => item.id === objectId)
    if (!target || !camera || !controls) return

    const box = new Box3().setFromObject(target.root)
    const center = box.getCenter(new Vector3())
    const size = box.getSize(new Vector3())
    const maxDim = Math.max(size.x, size.y, size.z, 0.5)
    const distance = maxDim * 2.2

    controls.target.copy(center)
    camera.position.set(center.x + distance, center.y + distance * 0.6, center.z + distance)
    camera.lookAt(center)
    controls.update()
  }

  function executeSceneAction(action: SceneActionPayload) {
    switch (action.action) {
      case 'move': {
        const target = objects.value.find(
          item => item.id === action.object_id || item.name === action.object_name
        )
        if (!target || !action.axis || action.distance === undefined) return
        target.root.position[action.axis] += action.distance
        applyHighlight(target.id)
        break
      }
      case 'rotate': {
        const target = objects.value.find(
          item => item.id === action.object_id || item.name === action.object_name
        )
        if (!target || !action.axis || action.degrees === undefined) return
        const radians = (action.degrees * Math.PI) / 180
        target.root.rotation[action.axis] += radians
        applyHighlight(target.id)
        break
      }
      case 'focus': {
        const id = action.object_id ?? objects.value.find(item => item.name === action.object_name)?.id
        if (id) focusObject(id)
        break
      }
      case 'highlight': {
        const id = action.object_id ?? objects.value.find(item => item.name === action.object_name)?.id
        if (id) applyHighlight(id)
        break
      }
      case 'clear_highlight':
        selectedObjectId.value = null
        clearHighlight()
        break
      default:
        break
    }
  }

  onUnmounted(() => {
    destroyScene()
  })

  return {
    containerRef,
    objects,
    selectedObjectId,
    selectedObject,
    objectSnapshots,
    loading,
    loadError,
    isReady,
    initScene,
    destroyScene,
    loadGlbFile,
    removeObject,
    focusObject,
    applyHighlight,
    clearHighlight,
    executeSceneAction
  }
}
