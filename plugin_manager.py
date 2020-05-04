# TODO: Start using pathlib for path manipulation
import os
import sys
import logging
import inspect
import importlib
from collections import Iterable, OrderedDict

logger = logging.getLogger(__name__)


class PluginError(Exception):
    pass


def extends(id):
    """
    Mark the function or method as extender to an extension point.

    :param id: Id of the extension point to extend
    :type id: str

    :returns: Decorated method.
    """
    def wrapper(fn):
        fn._extension_point = id
        return fn
    return wrapper


class ExtensionPoint(Iterable):
    """
    An extension point is a place where plugins can extend functionality.
    Extension points must have an unique id.
    """

    def __init__(self, id):
        """
        Initialize the extension point with an unique id
        :param id: extension point id
        :type id: str
        """
        self.id = id
        self.extenders = []
        self.extensions = []

    def reload_extensions(self):
        self.extensions = []
        for extender in self.extenders:
            extensions = extender()
            if not hasattr(extensions, "__iter__"):
                raise TypeError("extender method: {0} must return an iterable".format(extender))
            self.extensions.extend(extensions)

    def __iter__(self):
        return self

    def __get__(self, instance, owner):
        """
        Get all the extensions to this extension point. This is a lazy operation,
        extensions will be obtained the first time an extension point is accessed.
        """

        # Looked up using the class, not the object instance
        if instance is None:
            return self

        # return the cached contributions
        if self.extensions:
            return self.extensions

        # reload the contributions
        self.reload_extensions()

        return self.extensions

    def __set__(self, instance, value):
        raise AttributeError("Cannot assign values to an ExtensionPoint")

    def __str__(self):
        return self.id


class Plugin(object):
    """A plugin is an object that can declare extension points that other
    plugins can extend (plug in to) by means of extensions. A plugin
    can extend extension points declared by other plugins and itself.

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
    enabled: Enable or disable the plugin
    """

    _fields = (
        "id",
        "name",
        "version",
        "description",
        "platform",
        "author",
        "author_email",
        "depends",
        "enabled",
    )

    def __new__(cls, *args, **kwargs):
        instance = super(Plugin, cls).__new__(cls)

        # check if the plugin instance has declared all metadata fields
        for attr in cls._fields:
            if not hasattr(instance, attr):
                raise TypeError("Missing attribute: {0} in plugin: {1}".format(attr, cls.__name__))
        return instance

    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager

    @property
    def extension_points(self):
        """Return all extension points declared in this plugin.

        :returns: list(ExtensionPoint)
        """
        for attr in self.__class__.__dict__.values():
            if isinstance(attr, ExtensionPoint):
                yield attr

    @property
    def extenders(self):
        """Return all extenders declared in this plugin.

        :returns: list(callable)
        """
        for name, attr in self.__class__.__dict__.items():
            if callable(attr) and hasattr(attr, "_extension_point"):
                yield getattr(self, name)

    def configure(self):
        """Called by the plugin manager "configure_plugins" method to ask the plugin to configure itself.
        Subclasses my redefine this method to do configuration tasks.
        """
        pass

    def enable(self):
        """Called by the plugin manager to enable the plugin. Subclasses may
        redefine this method to do real work, for example, this is a good
        place to register services. This method is called after all extension
        point and contributions has been registered and the plugin has been
        configured.
        """
        pass

    def __str__(self):
        result = self.__class__.__name__ + ":\n"
        for attr in self._fields:
            result += "\t" + attr + ": " + str(getattr(self, attr)) + "\n"
        return result


class PluginManager(object):
    """The plugin manager is in charged to find, register and enable all plugins
    based on its dependencies. It searches for plugins in a list of file system paths.
    Also, the plugin manager has methods to register objects as services. Services
    are common python objects that are meant to be used by others. They are registered
    with a unique id so that later we can lookup for it using its id.
    """

    def __init__(self, search_path):
        """
        :param search_path: Search path to look for plugins
        :type search_path: str or list(str)
        """

        self.extension_points = {}
        self.services = {}
        self.disabled = []
        self._plugins = {}

        if isinstance(search_path, str):
            search_path = [search_path]
        self.search_path = (os.path.abspath(path) for path in search_path if os.path.exists(path))

    @property
    def plugins(self):
        """Return a list of plugins found. This list is sorted based on plugin dependencies.
        The result is cached for subsequent calls.

        :returns: list(Plugin)
        """
        def sort():
            sorted_plugins = []
            for id in self._plugins:
                for dep in self.dependencies(id):
                    if self._plugins[dep] not in sorted_plugins:
                        sorted_plugins.append(self._plugins[dep])
            return sorted_plugins

        if not hasattr(sort, "_sorted_plugins"):
            sort._sorted_plugins = sort()
        return sort._sorted_plugins

    def find_plugins(self, disabled_plugins=None):
        """Look for plugins in 'search_path' and register them with the plugin manager if they are enabled.

        :param disabled_plugins: An optional list of plugin ids to disable. Disabled plugins will be
            skipped by the discovery process

        :type disabled_plugins: iterable(str)
        """
        logger.debug("Starting plugin discovery process...")

        disabled_plugins = set(disabled_plugins) if disabled_plugins else set()
        for path in self.search_path:
            sys.path.append(path)
            for filename in os.listdir(path):
                # register individual plugins and its extension points
                plugin_path = os.path.join(path, filename)
                for plugin in self._loader(plugin_path):
                    disabled_dependencies = disabled_plugins.intersection(set(plugin.depends))
                    if not plugin.enabled:
                        logger.debug("Plugin disabled by default: {0}".format(plugin.id))
                        disabled_plugins.add(plugin.id)
                        self.disabled.append(plugin)
                        continue
                    elif plugin.id in disabled_plugins:
                        logger.debug("Plugin disabled by user: {0}".format(plugin.id))
                        self.disabled.append(plugin)
                        continue
                    elif disabled_dependencies:
                        msg = "Plugin disabled because of disabled dependencies: {0} --> [{1}]"
                        logger.debug(msg.format(plugin.id, ", ".join([pid for pid in disabled_dependencies])))
                        disabled_plugins.add(plugin.id)
                        self.disabled.append(plugin)
                        continue

                    logger.debug("Found plugin: {0}".format(plugin.id))
                    self._plugins.setdefault(plugin.id, plugin)

                    # register plugin's extension points
                    for extension_point in plugin.extension_points:
                        self.register_extension_point(extension_point)

        # register all plugin's extenders
        logger.debug("Registering all extenders")
        for plugin in self.plugins:
            for extender in plugin.extenders:
                self.register_extender(extender)

        logger.debug("Plugin discovery process finished.")

    def configure_plugins(self):
        """Run the configure for each plugin. The call order is based on plugin dependencies."""
        for plugin in self.plugins:
            logger.debug("Configuring plugin: {}".format(plugin.id))
            plugin.configure()

    def enable_plugins(self, notify=None):
        """Enable all discovered plugins. The order is based on plugin dependencies.

        :param notify: Callable used to notify when a plugin is about to be enabled and when the plugin is enabled.
        :type: callable(enabled, plugin) where "enabled" is False if the plugin is about to be enabled and True
            if the plugin is already enabled.
        """
        for plugin in self.plugins:
            # notify that the plugin is about to be enabled
            if callable(notify):
                notify(False, plugin)

            # enable the plugin
            logger.debug('Enabling plugin: {0}'.format(plugin.id))
            plugin.enable()

            # notify that the plugin has been enabled
            if callable(notify):
                notify(True, plugin)

    def register_extension_point(self, extension_point):
        logger.debug("Registering extension point: {}".format(extension_point.id))
        if extension_point.id in self.extension_points:
            raise PluginError("Duplicated extension point: {}".format(extension_point.id))
        self.extension_points[extension_point.id] = extension_point

    def remove_extension_point(self, extension_point):
        logger.debug("Removing extension point: {}".format(extension_point.id))
        if extension_point.id in self.extension_points:
            del self.extension_points[extension_point.id]

    def get_extension_point(self, extension_point_id):
        return self.extension_points.get(extension_point_id)

    def register_extender(self, extender):
        if not callable(extender) or not hasattr(extender, "_extension_point"):
            raise TypeError("An extender must be a callable decorated with: @extends")

        extension_point_id = getattr(extender, "_extension_point")
        if extension_point_id not in self.extension_points:
            raise PluginError("Unknown extension point: '{0}'".format(extension_point_id))

        logger.debug("Registering extender: {}.{} to extension point: {}".format(
            extender.__module__, extender.__name__, extension_point_id)
        )

        if extender not in self.extension_points[extension_point_id].extenders:
            self.extension_points[extension_point_id].extenders.append(extender)

    def remove_extender(self, extender):
        if not callable(extender) or not hasattr(extender, "_extension_point"):
            raise TypeError("An extender must be a callable decorated with: @contributes_to")

        extension_point_id = getattr(extender, "_extension_point")
        if extension_point_id not in self.extension_points:
            raise PluginError("Unknown extension point: '{0}'".format(extension_point_id))

        logger.debug("Removing extender from extension point: {}".format(extension_point_id))
        try:
            self.extension_points[extension_point_id].extenders.remove(extender)
        except ValueError:
            pass

    def register_service(self, id, service):
        """Register a service with the plugin manager. Raise a PluginError exception if there is an
        existing service with this id.

        :param id: Unique id of the service.
        :type id: str

        :param service: The service instance or a factory that create it.
            Factories can be any callable that return the service instance.
        :type: any or callable() -> service instance
        """
        if id in self.services:
            raise PluginError("Existing service: {0}".format(id))

        logger.debug("Registering service: {}".format(id))
        self.services[id] = service

    def remove_service(self, id):
        """Remove the service from the plugin manager. Raise a PluginError exception if there is no such service.

        :param id: Unique id of the service.
        :type id: str
        """
        if not id in self.services:
            raise PluginError("Service not found: {0}".format(id))

        logger.debug("Unregistering service: {}".format(id))
        del self.services[id]

    def get_service(self, id):
        """Lookup a service using its unique id. If the service was registered as a factory, then it will be called
        to create the real service and, any subsequent call will return the service created by the factory.

        :param id: Unique id of the service.
        :type id: str

        :returns: Service instance or None.
        """
        service = self.services.get(id)
        if callable(service):
            self.services[id] = service()
            return self.services[id]
        return service

    def dependencies(self, id, include_self=True):
        """Search for dependencies of this plugin and return it. This method does not analyze plugin versions.

        :param id: Unique id of the plugin
        :type id: str

        :param include_self: If this plugin id must be in the result list.
        :type include_self: bool

        :returns: List of plugin ids sorted by its dependencies.
        """
        def _resolve(id):
            unresolved.append(id)
            try:
                dependencies = self._plugins[id].depends
            except (KeyError, TypeError):
                raise PluginError("Missing plugin: {0}".format(id))

            for dep in dependencies:
                if dep not in self._plugins:
                    raise PluginError("Missing dependency: {0} for plugin: {1} ".format(dep, id))

                if dep not in resolved:
                    if dep in unresolved:
                        raise PluginError("Cyclic dependency detected: {0} --> {1}".format(id, dep))
                    _resolve(dep)

            resolved.append(id)
            unresolved.remove(id)

        resolved, unresolved = [], []
        _resolve(id)

        if include_self:
            return resolved
        return resolved[:-1]

    def _loader(self, plugin_path):
        """Load a plugin and return it. This function doesn't activate the plugin, just create an instance of it.

        :param plugin_path: The absolute path to the plugin
        :type plugin_path: str

        :returns: List of plugins found or an empty list.
        """

        name = None
        if os.path.isfile(plugin_path):
            if plugin_path.endswith(".zip"):
                package_name, ext = os.path.splitext(plugin_path)
                sys.path.insert(0, plugin_path)
                name = os.path.basename(package_name) + ".plugin_definitions"
            elif (plugin_path.endswith('.py') or plugin_path.endswith(".pyc")) and \
                    not os.path.basename(plugin_path).startswith('__init__'):
                name = os.path.splitext(os.path.basename(plugin_path))[0]
            else:
                return ()
        elif os.path.isdir(plugin_path):
            name = os.path.basename(plugin_path) + ".plugin_definitions"
        else:
            return ()

        try:
            plugin_definitions = importlib.import_module(name)
            plugins = [
                klass(self) for _, klass in
                inspect.getmembers(plugin_definitions, inspect.isclass)
                if (issubclass(klass, Plugin) and klass is not Plugin)
            ]
            return plugins
        except Exception as e:
            error = "error loading plugin: {0} in: {1}, reason: {2}"
            logger.error(error.format(os.path.basename(plugin_path), os.path.dirname(plugin_path), e))
            return ()

    def __str__(self):
        result = "Registered plugins: "
        for plugin in self.plugins:
            result += '\n\t' + str(plugin).replace('\t', '\t\t')
        return result
