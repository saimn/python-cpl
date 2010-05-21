import os
import sys
import tempfile
import pyfits

from restricteddict import RestrictedDict, RestrictedDictEntry
from log import msg

class FrameConfig(RestrictedDictEntry):
    '''Attributes:

    tag: tag name
    min: minimal number of frames, or None if not specified
    max: maximal number of frames, or None if not specified
    '''
    def __init__(self, tag, min_frames, max_frames, parent = None):
        RestrictedDictEntry.__init__(self, parent)
        self.tag = tag
        self.min = min_frames if min_frames > 0 else None
        self.max = max_frames if max_frames > 0 else None

    def extend_range(self, min_frames, max_frames):
        if self.min is not None:
            self.min = min(self.min, min_frames) if min_frames is not None \
                else None
        if self.max is not None:
            self.max = max(self.max, max_frames) if max_frames is not None \
                else None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "FrameDef('%s', value=%s)" % (
            self.tag, self.value.__repr__())

    def _doc(self):
        if self.max == 1:
            r = ' one frame'
        elif self.min > 1 and self.max > self.min:
            r = ' list of %i-%i frames' % (self.min, self.max)
        elif self.max > 1:
            r = ' one frame or list of max. %i frames' % self.max
        elif self.min > 1:
            r = ' list of min. %i frames' % self.max
        else:
            r = ' one frame or list of frames'
        if not self.min:
            r += ' (optional)'
        return r
    __doc__ = property(_doc)

class FrameList(RestrictedDict):
    def __init__(self, recipe, other = None):
        RestrictedDict.__init__(self, other)
        self._recipe = recipe

    def _key(self, p):
        return p.lower() if isinstance(p, str) else p.tag.lower()

    def __iter__(self):
        s = dict()
        for configs in self._recipe._recipe.frameConfig():
            c_cfg = configs[1]
            for f in c_cfg:
                fc = s.setdefault(f[0], 
                                  FrameConfig(f[0], f[1], f[2], self))
                fc.extend_range(f[1], f[2])
        return s.itervalues()
    
    def _doc(self):
        r = 'Frames for recipe %s.\n\nAttributes:\n' % (
            self._recipe.name)
        for s in self:
            r += '%s: %s\n' % (self._key(s), s.__doc__)
        return r        
    __doc__ = property(_doc)

    def _gettag(self, name):
        try:
            return self[name].tag
        except AttributeError:
            for t in self._recipe.tags:
                if name.lower() == t.lower():
                    return t
        return None

    def _aslist(self, *data, **ndata):
        frames = [ (f.tag, f.value) 
                   for f in self
                   if f.value and (ndata is None or f.tag not in ndata)
                   ] 
        if data:
            frames += [ ( self._recipe.tag, tdata ) for tdata in data ]
        if ndata:
            frames += [ ( self._gettag(name), tdata )
                        for name, tdata in ndata.items() 
                        if self._gettag(name)]

        framelist = list()
        for f in frames:
            if isinstance(f[1], list) and not isinstance(f[1], pyfits.HDUList):
                framelist += [ (f[0], frame) for frame in f[1] ]
            else:
                framelist.append((f[0], f[1]))
        return framelist

def mkabspath(frames, tmpdir):
    '''Convert all filenames in the frames list into absolute paths.

    Pyfits HDU lists will be converted to temporary files located in the 
    temporary directory tmpdir.

    The replacement is done in-place. The function will return the list of
    temporary files.

    param frames: List of (frame, tag) tuples with frame being either a file 
                  name or a HDU list.
    param tmpdir: directory where the temporary files are being created.
    '''
    
    tmpfiles = list()
    for i, frame in enumerate(frames):
        if isinstance(frame[1], pyfits.HDUList):
            tmpf = tempfile.mkstemp(prefix = '%s-' % frame[0],  
                                    suffix = '.fits', dir = tmpdir)
            os.close(tmpf[0])
            filename = os.path.abspath(tmpf[1])
            frames[i] = ( frame[0], filename )
            tmpfiles.append(filename)
            frame[1].writeto(filename)
        else:
            frames[i] = ( frame[0], os.path.abspath(frame[1]) )
    return tmpfiles

class Result(object):
    def __init__(self, recipedefs, res, delete = True):
        self.dir = os.getcwd()
        if res[0]:
            msg.info("Result frames:" )
            msg.indent_more()
            for tag, frame in res[0]:
                msg.info("%s = %s" % (tag, frame))
            msg.indent_less()
        
        if res[1][0]:
            msg.error("%s in %s" % (res[1][1], res[1][2]))
            raise CplError("%s in %s" % (res[1][1], res[1][2]))
        self.tags = set()
        for tag, frame in res[0]:
            hdu = pyfits.open(os.path.abspath(frame))
            if delete:
                os.remove(frame)
            tag = tag.lower()
            if tag.lower() not in self.__dict__:
                self.__dict__[tag] = hdu
                self.tags.add(tag)
            elif isinstance(self.__dict__[tag], pyfits.HDUList):
                self.__dict__[tag] = [ self.__dict__[tag], hdu ]
            else:
                self.__dict__[tag].append(hdu)

class CplError(Exception):
    pass

