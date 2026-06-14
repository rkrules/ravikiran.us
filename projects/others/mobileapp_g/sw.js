/**
 * Welcome to your Workbox-powered service worker!
 *
 * You'll need to register this file in your web app and you should
 * disable HTTP caching for this file too.
 * See https://goo.gl/nhQhGp
 *
 * The rest of the code is auto-generated. Please don't update this file
 * directly; instead, make changes to your Workbox build configuration
 * and re-run your build process.
 * See https://goo.gl/2aRDsh
 */

importScripts("workbox-v4.3.1/workbox-sw.js");
workbox.setConfig({modulePathPrefix: "workbox-v4.3.1"});

workbox.core.setCacheNameDetails({prefix: "gatsby-plugin-offline"});

workbox.core.skipWaiting();

workbox.core.clientsClaim();

/**
 * The workboxSW.precacheAndRoute() method efficiently caches and responds to
 * requests for URLs in the manifest.
 * See https://goo.gl/S9QRab
 */
self.__precacheManifest = [
  {
    "url": "webpack-runtime-59730dfcc6dc351fa803.js"
  },
  {
    "url": "styles.d77be72d189b9c8b2877.css"
  },
  {
    "url": "styles-6b8affa5cc22cb60670e.js"
  },
  {
    "url": "framework-2c421c5423d30cc6e0a0.js"
  },
  {
    "url": "app-2e179db02f46aca5d9bf.js"
  },
  {
    "url": "offline-plugin-app-shell-fallback/index.html",
    "revision": "87152a5c0da00e999360927fc4891ee1"
  },
  {
    "url": "component---cache-caches-gatsby-plugin-offline-app-shell-js-1cf1815cd9e7d53dcb02.js"
  },
  {
    "url": "page-data/offline-plugin-app-shell-fallback/page-data.json",
    "revision": "43232b01cc861c0701a3ece4bd67720b"
  },
  {
    "url": "page-data/app-data.json",
    "revision": "6ecba3250d8d29eeb311174d4c1c8d9b"
  },
  {
    "url": "252f366e-cac479adcd41432cb2a0.js"
  },
  {
    "url": "1bfc9850-f6fdf783382c5da86aeb.js"
  },
  {
    "url": "d7eeaac4-7a646d4ef66ec7de035c.js"
  },
  {
    "url": "component---src-pages-myaccounts-js-5ca70ab6da125ffec1b9.js"
  },
  {
    "url": "page-data/myaccounts/page-data.json",
    "revision": "ca9d803cda94fb8d189cfbf8cc7d9e11"
  },
  {
    "url": "component---src-pages-overview-js-321042a4bc867e5aa3ff.js"
  },
  {
    "url": "page-data/overview/page-data.json",
    "revision": "c528b0ff384e80bc051a8531ad671dd6"
  },
  {
    "url": "component---src-pages-contribution-overview-js-a2a4c6dfa93525de591a.js"
  },
  {
    "url": "page-data/contribution_overview/page-data.json",
    "revision": "7e31048c61ca82556fab4a9dc1c58fe7"
  },
  {
    "url": "component---src-pages-investments-js-346172a104d1db438544.js"
  },
  {
    "url": "page-data/investments/page-data.json",
    "revision": "72e1249092daecec43a8ca5f97b143b7"
  },
  {
    "url": "manifest.webmanifest",
    "revision": "6d7ab7c48bc2fd70e8444a465becab32"
  }
].concat(self.__precacheManifest || []);
workbox.precaching.precacheAndRoute(self.__precacheManifest, {});

workbox.routing.registerRoute(/(\.js$|\.css$|static\/)/, new workbox.strategies.CacheFirst(), 'GET');
workbox.routing.registerRoute(/^https?:.*\page-data\/.*\/page-data\.json/, new workbox.strategies.StaleWhileRevalidate(), 'GET');
workbox.routing.registerRoute(/^https?:.*\.(png|jpg|jpeg|webp|svg|gif|tiff|js|woff|woff2|json|css)$/, new workbox.strategies.StaleWhileRevalidate(), 'GET');
workbox.routing.registerRoute(/^https?:\/\/fonts\.googleapis\.com\/css/, new workbox.strategies.StaleWhileRevalidate(), 'GET');

/* global importScripts, workbox, idbKeyval */

importScripts(`idb-keyval-iife.min.js`)

const { NavigationRoute } = workbox.routing

let lastNavigationRequest = null
let offlineShellEnabled = true

// prefer standard object syntax to support more browsers
const MessageAPI = {
  setPathResources: (event, { path, resources }) => {
    event.waitUntil(idbKeyval.set(`resources:${path}`, resources))
  },

  clearPathResources: event => {
    event.waitUntil(idbKeyval.clear())
  },

  enableOfflineShell: () => {
    offlineShellEnabled = true
  },

  disableOfflineShell: () => {
    offlineShellEnabled = false
  },
}

self.addEventListener(`message`, event => {
  const { gatsbyApi: api } = event.data
  if (api) MessageAPI[api](event, event.data)
})

function handleAPIRequest({ event }) {
  const { pathname } = new URL(event.request.url)

  const params = pathname.match(/:(.+)/)[1]
  const data = {}

  if (params.includes(`=`)) {
    params.split(`&`).forEach(param => {
      const [key, val] = param.split(`=`)
      data[key] = val
    })
  } else {
    data.api = params
  }

  if (MessageAPI[data.api] !== undefined) {
    MessageAPI[data.api]()
  }

  if (!data.redirect) {
    return new Response()
  }

  return new Response(null, {
    status: 302,
    headers: {
      Location: lastNavigationRequest,
    },
  })
}

const navigationRoute = new NavigationRoute(async ({ event }) => {
  // handle API requests separately to normal navigation requests, so do this
  // check first
  if (event.request.url.match(/\/.gatsby-plugin-offline:.+/)) {
    return handleAPIRequest({ event })
  }

  if (!offlineShellEnabled) {
    return await fetch(event.request)
  }

  lastNavigationRequest = event.request.url

  let { pathname } = new URL(event.request.url)
  pathname = pathname.replace(new RegExp(`^/projects/others/mobileapp_g`), ``)

  // Check for resources + the app bundle
  // The latter may not exist if the SW is updating to a new version
  const resources = await idbKeyval.get(`resources:${pathname}`)
  if (!resources || !(await caches.match(`/projects/others/mobileapp_g/app-2e179db02f46aca5d9bf.js`))) {
    return await fetch(event.request)
  }

  for (const resource of resources) {
    // As soon as we detect a failed resource, fetch the entire page from
    // network - that way we won't risk being in an inconsistent state with
    // some parts of the page failing.
    if (!(await caches.match(resource))) {
      return await fetch(event.request)
    }
  }

  const offlineShell = `/projects/others/mobileapp_g/offline-plugin-app-shell-fallback/index.html`
  const offlineShellWithKey = workbox.precaching.getCacheKeyForURL(offlineShell)
  return await caches.match(offlineShellWithKey)
})

workbox.routing.registerRoute(navigationRoute)

// this route is used when performing a non-navigation request (e.g. fetch)
workbox.routing.registerRoute(/\/.gatsby-plugin-offline:.+/, handleAPIRequest)
