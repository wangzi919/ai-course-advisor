export const optionalAuth = (req, res, next) => { req.user = null; next(); };
