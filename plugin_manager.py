# python imports
import os
import sys
import logging
import inspect

# imagis imports
from .import_manager import ImportManager

logger = logging.getLogger(__name__)


class PluginError(Exception):
    def __init__(self, *args, **kwargs):
        super(PluginError, self).__init__(*args, **kwargs)


def contributes_to(id):
    """Decorator to be used in Plugin's methods to mark the method
    as contributor to an extension point.

    :param id: the id of the extension point to contributes to.
    :type id: str

    :returns: the decorated method.
    """
    def wrapper(fn):
        fn._extension_point = id
        return fn
    return wrapper


class ExtensionPoint(object):
    """An extension point is a place where plugins can contribute extensions
    by declaring methods as contributors to it. Extension points must have
    an unique id.
    """

    def __init__(self, id):
        """Initialize the extension point with an unique id"""
        self.id = id

    def __get__(self, instance, owner):
        """lazy get all contributed extensions."""

        if instance is None:
            return self

        contributions = []
        extension_points = PluginManager._extension_points
        for contributor in extension_points.get(self.id, []):
            result = contributor()
            if not hasattr(result, '__iter__'):
                error = 'contributor method: {method} must return an iterable'
                raise TypeError(error.format(method=contributor))
            contributions.extend(result)

        return contributions


class Plugin(object):
    """A plugin is an object that can declare extension points that other
    plugins can extend (plug in to) by means of contributions. A plugin
    can make contributions to extension points declared by other plugins
    and itself.
    Plugin subclasses must declare at least the following attributes:

    id: id of the plugin. Ej. id = 'imagis.plugins.core'
    name: human name of the plugin. Ej. name = 'Core Plugin'
    version: plugin version. Ej. version = "1.0"
    description: brief description of the plugin.
    platform: platform of the plugin. Ej.platform = ('Linux', 'Windows')
    author: author of the plugin. Ej. author = 'Jose M. Rodriguez Bacallao'
    author_email: mail address of the author. Ej. author_email = 'x@xx.com'
    depends: id's of the plugins that this plugin depends on.
        Ej. depends = ('imagis.plugins.core', 'imagis.plugins.shell')
            depends = []
    """

    _fields = (
        'id',
        'name',
        'version',
        'description',
        'platform',
        'author',
        'author_email',
        'depends',
        'enabled',
    )

    def __new__(cls, *args, **kwargs):
        instance = super(Plugin, cls).__new__(cls, *args, **kwargs)

        # check if the plugin instance has declared all metadata fields
        for attr in cls._fields:
            if not hasattr(instance, attr):
                error = 'attribute: "{attr}" of plugin: {plugin} is missing'
                raise TypeError(
                    error.format(attr=attr, plugin=cls.__name__)
                )
        return instance

    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager

    @property
    def extension_points(self):
        """Return an iterator over the list of extension points
        declared by this plugins.

        :returns: iter(ExtensionPoint)
        """
        for attr in self.__class__.__dict__.itervalues():
            if isinstance(attr, ExtensionPoint):
                yield attr

    @property
    def contributors(self):
        """Return an iterator over the list of contributors of this plugin.

        :returns: iter(callable)
        """
        for name, attr in self.__class__.__dict__.iteritems():
            if callable(attr) and hasattr(attr, '_extension_point'):
                yield getattr(self, name)

    def register_extension_points(self):
        """Called by the plugin manager to register all extension
        points declared by this plugin. This method is called
        before any contributor method is registered.
        """
        for extension_point in self.extension_points:
            PluginManager.register_extension_point(extension_point)

    def register_contributors(self):
        """Called by the plugin manager to register all contributor
        method of this plugin. This method is called after all
        extension points have been registered. If an extension point
        doesn't exist, an exception (PluginError) will be raised.
        """
        extension_points = PluginManager._extension_points
        for name, attr in self.__class__.__dict__.iteritems():
            if callable(attr) and hasattr(attr, '_extension_point'):
                if not attr._extension_point in extension_points:
                    error = 'unknow extension point: {id}'
                    raise PluginError(error.format(id=attr._extension_point))

                contributor = getattr(self, name)
                extension_point = contributor._extension_point
                extension_points[extension_point].append(contributor)

    def enable(self):
        """Called by the plugin manager to enable the plugin. Subclasses must
        redefine this method to do real work, for example, this is a good
        place to register services. This method is called after all extension
        point and contributions has been registered.
        """
        pass

    def register_service(self, id, service):
        """Register a service with the plugin manager. Raise a PluginError
        exception if there is an existing service with this id.

        :param id: the unique id of the service.
        :type id: str

        :param service: the service instance or a factory that create it.
            Factories can be any callable that return the service instance.
        :type: any or callable() -> service instance
        """
        self.plugin_manager.register_service(id, service)

    def unregister_service(self, id):
        """Unregister the service from the plugin manager. Raise a PluginError
        exception if there is no such service.

        :param id: the unique id of the service.
        :type id: str
        """
        self.plugin_manager.unregister_service(id)

    def get_service(self, id):
        """Lookup a service using its unique id. If the service was registered
        as a factory, then it will be called to create the real service and,
        any subsequent call will return the service created by the factory.

        :param id: the unique id of the service.
        :type id: str

        :returns: the service instance or None.
        """
        return self.plugin_manager.get_service(id)

    def __str__(self):
        result = self.__class__.__name__ + ':\n'
        for attr in self._fields:
            result += '\t' + attr + ': ' + str(getattr(self, attr)) + '\n'
        return result


class PluginManager(object):
    """The plugin manager is in charged to find, register and enable
    all plugins based on its dependencies. It search for plugins in
    a list of file system paths. Also, the plugin manager has methods
    to register objects as services.
    Services are common python objects that are mean to be used by
    others. They are registered with an unique id so that later we
    can lookup for it using its id.
    """

    _extension_points = {}
    _services = {}
    _plugins = {}
    disabled_plugins = {}

    def __init__(self, search_path):
        """Initialize the plugin manager loading the information of plugins
        contained in all path specified by search_path.

        :param search_path: the search path for plugins
        :type search_path: str or list(str)
        """
        self._plugins = PluginManager._plugins

        if isinstance(search_path, basestring):
            search_path = [search_path]

        self.search_path = (
            os.path.abspath(path) for path in search_path
            if os.path.exists(path)
        )

        self.collect_plugins()

    @classmethod
    def register_extension_point(cls, extension_point):
        cls._extension_points[extension_point.id] = []

    @property
    def plugins(self):
        """Return a list of found plugins. This list is sorted based on
        plugin dependencies. The result is cached for subsequent calls.

        :returns: list(Plugin)
        """
        def sort():
            sorted_plugins = []
            plugins = self._plugins
            for id in plugins:
                for dep in self.dependencies(id):
                    if plugins[dep] not in sorted_plugins:
                        sorted_plugins.append(plugins[dep])
            return sorted_plugins

        if not hasattr(sort, '_sorted_plugins'):
            sort._sorted_plugins = sort()
        return sort._sorted_plugins

    def collect_plugins(self):
        """Look for plugins in 'search_path' and register them with
        the plugin manager
        """
        for path in self.search_path:
            sys.path.append(path)
            for filename in os.listdir(path):
                # check for possible valid plugins
                loader = lambda _: ()
                plugin_path = os.path.join(path, filename)
                if os.path.isfile(plugin_path):
                    if filename.endswith('.zip'):
                        loader = self._zip_plugin_loader
                    elif filename.endswith('.egg'):
                        loader = self._egg_plugin_loader
                elif os.path.isdir(plugin_path):
                    loader = self._package_plugin_loader

                # register individual plugins and its extension points
                for plugin in loader(plugin_path):
                    if plugin.enabled:
                        logger.info('found plugin: {id}'.format(id=plugin.id))
                        self._plugins.setdefault(plugin.id, plugin)
                        plugin.register_extension_points()
                    else:
                        logger.info('plugin: {id} disabled'.format(id=plugin.id))
                        self.disabled_plugins.setdefault(plugin.id, plugin)

        # HACK: this is a hack to remove enabled plugins
        # that have missing dependencies. Rethink again!!!
        try:
            for plugin in self.plugins:
                pass
        except PluginError:
            msg = 'disabling plugin: {id} due to missing dependencies'
            logger.error(msg.format(id=plugin.id))
            self.disabled_plugins[plugin.id] = self._plugins.pop(plugin.id)

        # register all extension points contributors
        for plugin in self.plugins:
            plugin.register_contributors()

    def enable_plugins(self, notify=None):
        """"Enable all discovered plugins. The enabling order is based on
        plugin dependencies.

        :param notify: callable used to notify when a plugin is about to be
            enabled and when the plugin is enabled.
        :type: callable(enabled, plugin) where "enabled" is False if the
            plugin is about to be enabled and True if the plugin is
            already enabled.
        """
        for plugin in self.plugins:
            logger.info('enabling plugin: {id}'.format(id=plugin.id))

            # notify that the plugin is about to be enabled
            if callable(notify):
                notify(False, plugin)

            # enable the plugin
            plugin.enable()

            # notify that the plugin has beem enabled
            if callable(notify):
                notify(True, plugin)

    def register_service(self, id, service):
        """Register a service with the plugin manager. Raise a PluginError
        exception if there is an existing service with this id.

        :param id: the unique id of the service.
        :type id: str

        :param service: the service instance or a factory that create it.
            Factories can be any callable that return the service instance.
        :type: any or callable() -> service instance
        """
        if id in self._services:
            raise PluginError('Existing service: {id}'.format(id=id))
        self._services[id] = service

    def unregister_service(self, id):
        """Unregister the service from the plugin manager. Raise a PluginError
        exception if there is no such service.

        :param id: the unique id of the service.
        :type id: str
        """
        if not id in self._services:
            raise PluginError('Service not found: {id}'.format(id=id))
        del self._services[id]

    def get_service(self, id):
        """Lookup a service using its unique id. If the service was registered
        as a factory, then it will be called to create the real service and,
        any subsequent call will return the service created by the factory.

        :param id: the unique id of the service.
        :type id: str

        :returns: the service instance or None.
        """
        service = self._services.get(id)
        if callable(service):
            self._services[id] = service()
            return self._services[id]
        return service

    def dependencies(self, id, include_self=True):
        """Search for dependencies of this plugin and return it.
        This method does not analyze plugin versions.

        :param id: the id of the plugin
        :type id: str

        :param include_self: if this plugin id must be in the result list.
        :type include_self: bool

        :returns: list of plugin ids sorted by its dependencies.
        """
        def _resolve(id):
            unresolved.append(id)
            try:
                dependencies = self._plugins[id].depends
            except (KeyError, TypeError):
                raise PluginError('Missing plugin: {id}'.format(id=id))

            for dep in dependencies:
                if dep not in self._plugins:
                    raise PluginError('Missing plugin: {id}'.format(id=dep))

                if dep not in resolved:
                    if dep in unresolved:
                        error = 'Cyclic dependency detected: {src} --> {dst}'
                        raise PluginError(error.format(src=id, dst=dep))
                    _resolve(dep)

            resolved.append(id)
            unresolved.remove(id)

        resolved, unresolved = [], []
        _resolve(id)

        if include_self:
            return resolved
        return resolved[:-1]

    def _package_plugin_loader(self, plugin_path):
        """Load a plugin and return it. This function does't
        activate the plugin, just create an instance of it.

        :param plugin_path: the absolute path to the plugin
        :type plugin_path: str

        :returns: the list of individuals plugins found in the plugin
            definiton file of the plugin or an empty list.
        """
        if not os.path.isdir(plugin_path):
            return None

        try:
            plugin_definitions = ImportManager.import_module(
                os.path.basename(plugin_path) + '.plugin_definitions'
            )
            plugins = [
                klass(self) for _, klass in
                inspect.getmembers(plugin_definitions, inspect.isclass)
                if (issubclass(klass, Plugin) and klass is not Plugin)
            ]
            return plugins
        except Exception as e:
            error = 'error loading plugin: {name} in: {path}, reason: {reason}'
            logger.error(error.format(
                name=os.path.basename(plugin_path),
                path=os.path.dirname(plugin_path),
                reason=str(e)
            ))
            return ()

    def _zip_plugin_loader(self, plugin_path):
        """Load a plugin and return it. This function does't
        activate the plugin, just create an instance of it.

        :param plugin_path: the absolute path to the plugin
        :type plugin_path: str

        :returns: the list of individuals plugins found in the plugin
            definiton file of the plugin or an empty list.
        """
        package_name, ext = os.path.splitext(plugin_path)
        if not os.path.isfile(plugin_path) and  ext != '.zip':
            return None

        try:
            # add the zip file to python path for correct import
            sys.path.insert(0, plugin_path)
            plugin_definitions = ImportManager.import_module(
                os.path.basename(package_name) + '.plugin_definitions'
            )
            plugins = [
                klass(self) for _, klass in
                inspect.getmembers(plugin_definitions, inspect.isclass)
                if (issubclass(klass, Plugin) and klass is not Plugin)
            ]
            return plugins
        except Exception as e:
            error = 'error loading plugin: {name} in: {path}, reason: {reason}'
            logger.error(error.format(
                name=os.path.basename(plugin_path),
                path=os.path.dirname(plugin_path),
                reason=str(e)
            ))
            return ()

    def _egg_plugin_loader(self, plugin_path):
        # TODO: implement plugin loader for egg plugins
        return ()

    def __str__(self):
        result = 'Registered plugins: '
        for plugin in self.plugins:
            result += '\n\t' + str(plugin).replace('\t', '\t\t')
        return result
