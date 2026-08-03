/**
 * 注入到已登录的群相册页面，通过 window.__QQAlbumAPI 暴露能力。
 */
(function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function groupIdFromPage() {
    try {
      return (
        new URLSearchParams(location.search).get('groupId') ||
        (window.GroupZone && GroupZone.GPHOTO && GroupZone.GPHOTO.groupId) ||
        ''
      );
    } catch (e) {
      return '';
    }
  }

  function isReady() {
    try {
      return !!(
        window.GroupZone &&
        GroupZone.GPHOTO &&
        GroupZone.GPHOTO.logic &&
        typeof GroupZone.GPHOTO.logic.getAlbumList === 'function' &&
        window.seajs
      );
    } catch (e) {
      return false;
    }
  }

  function getAlbumList(start, num) {
    return new Promise((resolve, reject) => {
      GroupZone.GPHOTO.logic.getAlbumList(
        resolve,
        (err) => {
          let msg = 'getAlbumList failed';
          try {
            if (typeof err === 'string') msg = err;
            else if (err && (err.message || err.msg)) msg = String(err.message || err.msg);
            else if (err) msg = JSON.stringify(err);
          } catch (e) {}
          reject(new Error(msg));
        },
        start === 0,
        start,
        num,
        0
      );
    });
  }

  function getDownUrl(params) {
    return new Promise((resolve, reject) => {
      seajs.use('photo.v7/common/api/download/index', (mod) => {
        mod.getDownUrl(params).done(resolve).fail(reject);
      });
    });
  }

  function getPhotoList(albumId, start, num, attach_info) {
    return new Promise((resolve, reject) => {
      GroupZone.GPHOTO.logic.getPhotoList(
        albumId,
        null,
        { start: start, num: num, attach_info: attach_info || '' },
        resolve,
        reject
      );
    });
  }

  async function listAlbums() {
    const PAGE = 100;
    let all = [];
    let start = 0;
    let total = 0;
    while (true) {
      const page = await getAlbumList(start, PAGE);
      if (!page) throw new Error('getAlbumList 返回空');
      total = page.total || 0;
      const batch = page.album || page.albums || [];
      all = all.concat(batch);
      if (all.length >= total || !batch.length) break;
      start += PAGE;
      await sleep(200);
    }
    return all.map((a) => ({
      id: a.id,
      title: a.title || '',
      photoCount: a.photocnt || a.photo_count || a.photoCount || 0,
      desc: a.desc || '',
    }));
  }

  async function getAlbumZipUrl(albumId, title) {
    const gid = groupIdFromPage();
    const resp = await getDownUrl({
      appid: 422,
      selectMode: 1,
      albumid: albumId,
      hostid: gid,
      albumName: title || '',
    });
    return {
      code: resp.code,
      message: resp.message || '',
      downloadUrl: (resp.data && resp.data.downloadUrl) || '',
      photoTotal: (resp.data && resp.data.photoTotal) || 0,
    };
  }

  async function getBatchZipUrl(albumId, title, photoIds) {
    const gid = groupIdFromPage();
    const resp = await getDownUrl({
      appid: 422,
      selectMode: 0,
      albumid: albumId,
      photos: (photoIds || []).join('_'),
      hostid: gid,
      albumName: title || '',
    });
    return {
      code: resp.code,
      message: resp.message || '',
      downloadUrl: (resp.data && resp.data.downloadUrl) || '',
      photoTotal: (resp.data && resp.data.photoTotal) || 0,
    };
  }

  async function listPhotos(albumId) {
    const seen = new Set();
    const all = [];
    let attach_info = '';
    let total = 0;
    let pages = 0;
    while (pages < 500) {
      const list = await getPhotoList(albumId, all.length, 40, attach_info);
      total = list.total || 0;
      const batch = list.photo || list.photos || [];
      if (!batch.length) break;
      let added = 0;
      for (const p of batch) {
        if (!p || !p.id || seen.has(p.id)) continue;
        seen.add(p.id);
        added += 1;
        all.push({
          id: p.id,
          name: p.name || '',
          videoflag: !!p.videoflag,
          hasraw: !!p.hasraw,
          url: p.url || '',
          burl: p.burl || '',
          hdurl: p.hdurl || '',
          rawurl: typeof p.rawurl === 'string' ? p.rawurl : '',
          videourl: p.videourl || '',
        });
      }
      attach_info = list.attach_info || '';
      pages += 1;
      if (!list.hasmore || all.length >= total || added === 0) break;
      await sleep(80);
    }
    return { total: total, photos: all };
  }

  window.__QQAlbumAPI = {
    isReady: isReady,
    groupId: groupIdFromPage,
    listAlbums: listAlbums,
    getAlbumZipUrl: getAlbumZipUrl,
    getBatchZipUrl: getBatchZipUrl,
    listPhotos: listPhotos,
  };

  return { ok: true, ready: isReady() };
})();
