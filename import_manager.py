

class ImportManager(object):
    """ Import the symbol defined by the specified symbol path.

        'symbol_path' is a string containing the path to a symbol through the
        Python package namespace.

        It can be in one of two forms:

        1) 'foo.bar.baz'

           Which is turned into the equivalent of an import statement that
           looks like::

             from foo.bar import baz

           With the value of 'baz' being returned.

        2) 'foo.bar:baz' (i.e. a ':' separating the module from the symbol)

           Which is turned into the equivalent of::

             from foo import bar
             eval('baz', bar.__dict__)

           With the result of the 'eval' being returned.

        The second form is recommended as it allows for nested symbols to be
        retreived, e.g. the symbol path 'foo.bar:baz.bling' becomes::

            from foo import bar
            eval('baz.bling', bar.__dict__)

        The first form is retained for backwards compatability.

    """

    @staticmethod
    def import_symbol(symbol_path):
        """ Import the symbol defined by the specified symbol path.

        :param symbol_path: a path of the form of: foo.bar.baz or foo.bar:baz
        :type symbol_path: str

        :returns: the imported symbol
        """

        if ':' in symbol_path:
            module_name, symbol_name = symbol_path.split(':')

            module = ImportManager.import_module(module_name)
            symbol = eval(symbol_name, module.__dict__)

        else:
            components = symbol_path.split('.')

            module_name = '.'.join(components[:-1])
            symbol_name = components[-1]

            module = __import__(
                module_name, globals(), locals(), [symbol_name]
            )

            symbol = getattr(module, symbol_name)

        return symbol

    @staticmethod
    def import_module(module_name):
        """ Import the module with the specified (and possibly dotted) name.

        :param module_name: a path in the form of: foo.bar.module
        :type module_name: str

        :returns: the imported module
        """
        module = __import__(module_name)

        components = module_name.split('.')
        for component in components[1:]:
            module = getattr(module, component)

        return module
